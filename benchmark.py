"""
Benchmark the translation system against official reference translations.

Source corpus: Universal Declaration of Human Rights (UDHR) — public domain.
Official Hindi translations from the UN/OHCHR.

Usage:
    uv run python benchmark.py                  # run with config.yaml model
    uv run python benchmark.py --google         # also compare with Google Translate
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from translation_engine import TranslationEngine
from evaluation import TranslationEvaluator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("benchmark.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# UDHR parallel sentences  (English → Hindi, official UN translations)
# ---------------------------------------------------------------------------
UDHR_SAMPLES: List[Dict[str, str]] = [
    {
        "source": "All human beings are born free and equal in dignity and rights.",
        "reference_hi": "सभी मनुष्यों को गौरव और अधिकारों के मामले में जन्मजात स्वतन्त्रता और समानता प्राप्त है।",
    },
    {
        "source": "Everyone has the right to life, liberty and security of person.",
        "reference_hi": "प्रत्येक व्यक्ति को जीवन, स्वाधीनता और वैयक्तिक सुरक्षा का अधिकार है।",
    },
    {
        "source": "No one shall be held in slavery or servitude.",
        "reference_hi": "किसी को भी दासता या गुलामी में नहीं रखा जायेगा।",
    },
    {
        "source": "No one shall be subjected to torture or to cruel, inhuman or degrading treatment or punishment.",
        "reference_hi": "किसी को भी यातना या क्रूर, अमानवीय अथवा अपमानजनक व्यवहार या दंड नहीं दिया जायेगा।",
    },
    {
        "source": "Everyone has the right to freedom of thought, conscience and religion.",
        "reference_hi": "प्रत्येक व्यक्ति को विचार, अन्तरात्मा और धर्म की स्वतन्त्रता का अधिकार है।",
    },
    {
        "source": "Everyone has the right to freedom of opinion and expression.",
        "reference_hi": "प्रत्येक व्यक्ति को विचार और अभिव्यक्ति की स्वतन्त्रता का अधिकार है।",
    },
    {
        "source": "Everyone has the right to education.",
        "reference_hi": "प्रत्येक व्यक्ति को शिक्षा का अधिकार है।",
    },
    {
        "source": "Everyone has the right to work and to free choice of employment.",
        "reference_hi": "प्रत्येक व्यक्ति को काम करने और स्वतन्त्र रूप से रोजगार चुनने का अधिकार है।",
    },
    {
        "source": "Everyone has the right to a standard of living adequate for the health and well-being of himself and of his family.",
        "reference_hi": "प्रत्येक व्यक्ति को अपने और अपने परिवार के स्वास्थ्य और कल्याण के लिए पर्याप्त जीवन स्तर का अधिकार है।",
    },
    {
        "source": "All are equal before the law and are entitled without any discrimination to equal protection of the law.",
        "reference_hi": "सभी लोग कानून के समक्ष समान हैं और बिना किसी भेदभाव के कानून के समान संरक्षण के हकदार हैं।",
    },
]


# ---------------------------------------------------------------------------
# Translation helpers
# ---------------------------------------------------------------------------

def translate_with_system(source_texts: List[str], config: dict) -> tuple[List[str], float]:
    """Translate sentences using the project's TranslationEngine. Returns (translations, elapsed_s)."""
    engine = TranslationEngine(config)
    logger.info(f"Translating {len(source_texts)} sentences with {config.get('llm_model')}...")
    start = time.time()
    translated = engine.translate_batch(source_texts, batch_index=0)
    elapsed = round(time.time() - start, 1)
    return translated, elapsed


def translate_with_google(source_texts: List[str], target_lang: str = "hi") -> List[str]:
    """Translate via Google Translate (requires: uv add deep-translator)."""
    try:
        from deep_translator import GoogleTranslator
        gt = GoogleTranslator(source="auto", target=target_lang)
        return [gt.translate(text) for text in source_texts]
    except ImportError:
        logger.error("deep-translator not installed. Run: uv add deep-translator")
        return []
    except Exception as e:
        logger.error(f"Google Translate error: {e}")
        return []


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def write_benchmark_report(
    our_hyps: List[str],
    our_metrics: dict,
    our_elapsed: float,
    sources: List[str],
    references: List[str],
    model: str,
    google_hyps: List[str] | None = None,
    google_metrics: dict | None = None,
) -> None:
    lines = [
        "=" * 65,
        "  BENCHMARK REPORT",
        "  Corpus : UDHR Parallel Corpus (10 sentences, English → Hindi)",
        "=" * 65,
        f"  Model          : {model}",
        f"  Inference time : {our_elapsed}s",
        "",
        "  ── OUR SYSTEM ──────────────────────────────────────────────",
        f"  BLEU  : {our_metrics.get('bleu', 'N/A')}   {our_metrics.get('bleu_interpretation', '')}",
        f"  chrF  : {our_metrics.get('chrf', 'N/A')}   {our_metrics.get('chrf_interpretation', '')}",
    ]

    if google_metrics:
        lines += [
            "",
            "  ── GOOGLE TRANSLATE ────────────────────────────────────────",
            f"  BLEU  : {google_metrics.get('bleu', 'N/A')}   {google_metrics.get('bleu_interpretation', '')}",
            f"  chrF  : {google_metrics.get('chrf', 'N/A')}   {google_metrics.get('chrf_interpretation', '')}",
        ]

    lines += [
        "",
        "  ── SENTENCE-LEVEL DETAIL ───────────────────────────────────",
    ]
    for i, (src, hyp, ref) in enumerate(zip(sources, our_hyps, references), 1):
        lines.append(f"  [{i:02d}] Source    : {src}")
        lines.append(f"       Our        : {hyp}")
        if google_hyps and i <= len(google_hyps):
            lines.append(f"       Google     : {google_hyps[i - 1]}")
        lines.append(f"       Reference  : {ref}")
        lines.append("")

    lines.append("=" * 65)
    report = "\n".join(lines)

    output_path = "benchmark_report.txt"
    Path(output_path).write_text(report + "\n", encoding="utf-8")
    logger.info("\n" + report)
    logger.info(f"Full report saved to: {output_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_benchmark(include_google: bool = False) -> None:
    config_manager = Config()
    config = config_manager.config

    if config.get('target_language', 'Hindi').lower() != 'hindi':
        logger.warning(
            f"Benchmark references are in Hindi but target_language='{config['target_language']}'. "
            "Scores will not be meaningful."
        )

    sources = [s['source'] for s in UDHR_SAMPLES]
    references = [s['reference_hi'] for s in UDHR_SAMPLES]

    evaluator = TranslationEvaluator()

    # Our system
    our_hyps, elapsed = translate_with_system(sources, config)
    logger.info("\n── Our System ──")
    our_metrics = evaluator.evaluate_document(our_hyps, references)

    # Optional Google Translate comparison
    google_hyps: List[str] = []
    google_metrics: dict = {}
    if include_google:
        logger.info("\n── Google Translate ──")
        google_hyps = translate_with_google(sources, target_lang="hi")
        if google_hyps:
            google_metrics = evaluator.evaluate_document(google_hyps, references)

    write_benchmark_report(
        our_hyps=our_hyps,
        our_metrics=our_metrics,
        our_elapsed=elapsed,
        sources=sources,
        references=references,
        model=config.get('llm_model', 'unknown'),
        google_hyps=google_hyps or None,
        google_metrics=google_metrics or None,
    )

    # Also write the standard evaluation_report.txt with sentence-level detail
    evaluator.write_report(our_metrics, hypotheses=our_hyps, output_path="evaluation_report.txt")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark the translation system.")
    parser.add_argument(
        "--google",
        action="store_true",
        help="Include a Google Translate comparison (requires googletrans package).",
    )
    args = parser.parse_args()
    run_benchmark(include_google=args.google)
