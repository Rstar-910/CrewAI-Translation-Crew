"""Translation quality evaluation using BLEU and chrF metrics (sacrebleu)."""

from __future__ import annotations

import logging
from pathlib import Path
from statistics import mean
from typing import List, Dict, Any, Optional

try:
    from sacrebleu.metrics import BLEU, CHRF
    SACREBLEU_AVAILABLE = True
except ImportError:
    SACREBLEU_AVAILABLE = False

logger = logging.getLogger(__name__)

_BLEU_THRESHOLDS = [
    (40, "High quality — approaches human translation"),
    (20, "Understandable — core meaning conveyed"),
    (0,  "Low quality — significant errors likely"),
]
_CHRF_THRESHOLDS = [
    (60, "High quality"),
    (40, "Acceptable"),
    (0,  "Needs improvement"),
]
# Warn loudly when truncation drops more than this fraction of the corpus
_MISMATCH_ERROR_THRESHOLD = 0.20


def _interpret(score: float, thresholds: list) -> str:
    for cutoff, label in thresholds:
        if score >= cutoff:
            return label
    return ""


class TranslationEvaluator:
    """Computes corpus-level and sentence-level BLEU and chrF using sacrebleu."""

    def __init__(self):
        if not SACREBLEU_AVAILABLE:
            raise ImportError(
                "sacrebleu is required for evaluation.\n"
                "  uv add sacrebleu   (or pip install sacrebleu)"
            )
        self.bleu = BLEU(effective_order=True)
        self.chrf = CHRF()

    # ------------------------------------------------------------------
    # Core scorer
    # ------------------------------------------------------------------

    def compute(self, hypotheses: List[str], references: List[str]) -> Dict[str, Any]:
        """
        Compute corpus-level and sentence-level BLEU and chrF.

        Returns
        -------
        dict with keys:
          bleu, chrf              — corpus-level scores (float)
          bleu_interpretation,
          chrf_interpretation     — human-readable labels
          bleu_detail             — full sacrebleu corpus string
          sentence_bleu           — per-sentence BLEU list
          sentence_chrf           — per-sentence chrF list
          worst_chrf_indices      — indices of the 5 lowest chrF sentences
        """
        # Corpus-level
        bleu_result = self.bleu.corpus_score(hypotheses, [references])
        chrf_result = self.chrf.corpus_score(hypotheses, [references])

        bleu_score = round(bleu_result.score, 2)
        chrf_score = round(chrf_result.score, 2)

        # Sentence-level
        sentence_bleu = [
            round(self.bleu.sentence_score(h, [r]).score, 2)
            for h, r in zip(hypotheses, references)
        ]
        sentence_chrf = [
            round(self.chrf.sentence_score(h, [r]).score, 2)
            for h, r in zip(hypotheses, references)
        ]

        # Bottom-5 by chrF — these are the paragraphs to flag for human review
        worst_indices = [
            i for i, _ in sorted(enumerate(sentence_chrf), key=lambda x: x[1])[:5]
        ]

        return {
            'bleu': bleu_score,
            'chrf': chrf_score,
            'bleu_interpretation': _interpret(bleu_score, _BLEU_THRESHOLDS),
            'chrf_interpretation': _interpret(chrf_score, _CHRF_THRESHOLDS),
            'bleu_detail': str(bleu_result),
            'sentence_bleu': sentence_bleu,
            'sentence_chrf': sentence_chrf,
            'worst_chrf_indices': worst_indices,
        }

    # ------------------------------------------------------------------
    # Document-level evaluation
    # ------------------------------------------------------------------

    def evaluate_document(
        self,
        hypotheses: List[str],
        references: List[str],
        mode: str = 'reference',
    ) -> Dict[str, Any]:
        """
        Evaluate hypotheses against references.

        Parameters
        ----------
        hypotheses  : translations produced by the system
        references  : ground-truth references  OR  original source texts
                      (when mode='back_translation')
        mode        : 'reference'         — ground-truth evaluation
                      'back_translation'  — proxy using back-translated texts
        """
        hyps, refs = list(hypotheses), list(references)

        # -- Fix 4: length mismatch — log exactly what gets dropped, error if >20% --
        if len(hyps) != len(refs):
            min_len = min(len(hyps), len(refs))
            n_dropped = abs(len(hyps) - len(refs))
            drop_pct = n_dropped / max(len(hyps), len(refs))
            dropped_side = "hypotheses" if len(hyps) > len(refs) else "references"

            msg = (
                f"Length mismatch: {len(hyps)} hypotheses vs {len(refs)} references. "
                f"Dropping {n_dropped} excess {dropped_side} "
                f"(indices {min_len}–{min_len + n_dropped - 1}, "
                f"{drop_pct:.0%} of corpus)."
            )
            if drop_pct > _MISMATCH_ERROR_THRESHOLD:
                logger.error(
                    msg + " Drop rate exceeds 20% — scores will be unreliable. "
                    "Verify that reference_doc has exactly one line per translated paragraph."
                )
            else:
                logger.warning(msg)

            hyps, refs = hyps[:min_len], refs[:min_len]

        metrics = self.compute(hyps, refs)
        metrics['mode'] = mode
        metrics['n_evaluated'] = len(hyps)

        # Log summary
        bleu_label = "Proxy BLEU (back-translation)" if mode == 'back_translation' else "BLEU"
        logger.info(f"{bleu_label:<30} : {metrics['bleu']:.2f}  ({metrics['bleu_interpretation']})")
        logger.info(f"{'chrF':<30} : {metrics['chrf']:.2f}  ({metrics['chrf_interpretation']})")

        sc = metrics['sentence_chrf']
        if sc:
            logger.info(
                f"{'chrF sentence range':<30} : "
                f"{min(sc):.2f} – {max(sc):.2f}  (mean {mean(sc):.2f})"
            )

        return metrics

    # ------------------------------------------------------------------
    # Report writer
    # ------------------------------------------------------------------

    def write_report(
        self,
        metrics: Dict[str, Any],
        hypotheses: Optional[List[str]] = None,
        output_path: str = "evaluation_report.txt",
    ) -> str:
        """Write a human-readable evaluation report to disk and return it as a string."""
        bleu  = metrics.get('bleu')
        chrf  = metrics.get('chrf')
        mode  = metrics.get('mode', 'reference')

        bleu_str  = f"{bleu:.2f}" if bleu is not None else "N/A"
        chrf_str  = f"{chrf:.2f}" if chrf is not None else "N/A"
        bleu_label = "BLEU Score (proxy — back-translation)" if mode == 'back_translation' else "BLEU Score"

        lines = [
            "=" * 62,
            "  TRANSLATION EVALUATION REPORT",
            "=" * 62,
            f"  Mode           : {mode}",
            f"  Paragraphs     : {metrics.get('n_evaluated', 'N/A')}",
            "",
            f"  {bleu_label:<40}: {bleu_str:>6}   {metrics.get('bleu_interpretation', '')}",
            f"  {'chrF Score':<40}: {chrf_str:>6}   {metrics.get('chrf_interpretation', '')}",
            "",
            "  Score Guide:",
            "  BLEU  > 40  →  High quality (near human)",
            "  BLEU 20–40  →  Understandable",
            "  BLEU  < 20  →  Low quality",
            "",
            "  chrF  > 60  →  High quality",
            "  chrF 40–60  →  Acceptable",
            "  chrF  < 40  →  Needs improvement",
        ]

        # Sentence-level stats block
        sc = metrics.get('sentence_chrf', [])
        if sc:
            lines += [
                "",
                "  ── Sentence-level chrF ─────────────────────────────────",
                f"  Min  : {min(sc):.2f}",
                f"  Mean : {mean(sc):.2f}",
                f"  Max  : {max(sc):.2f}",
            ]
            worst = metrics.get('worst_chrf_indices', [])
            if worst:
                lines.append("")
                lines.append("  Paragraphs to flag for human review (lowest chrF):")
                for idx in worst:
                    if idx < len(sc):
                        preview = ""
                        if hypotheses and idx < len(hypotheses):
                            raw = hypotheses[idx]
                            preview = (raw[:70] + "…") if len(raw) > 70 else raw
                        lines.append(f"  [{idx + 1:04d}] chrF {sc[idx]:.2f}  {preview}")

        if metrics.get('bleu_detail'):
            lines += ["", f"  Detail : {metrics['bleu_detail']}"]

        if mode == 'back_translation':
            lines += [
                "",
                "  NOTE: Scores above are back-translation proxies, not ground-truth",
                "  BLEU. Set reference_doc in config.yaml for true evaluation.",
            ]

        lines.append("=" * 62)
        report = "\n".join(lines)
        Path(output_path).write_text(report + "\n", encoding="utf-8")
        logger.info(f"Evaluation report saved to: {output_path}")
        logger.info("\n" + report)
        return report


def load_references(path: str) -> List[str]:
    """Load reference translations from a plain-text file (one line per paragraph)."""
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
