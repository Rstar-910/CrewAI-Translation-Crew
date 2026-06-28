# CrewAI Translation Crew

A **three-agent** document translation system built with [CrewAI](https://github.com/joaomdmoura/crewAI) and [Ollama](https://ollama.com). Translates `.docx` files into a target language while preserving formatting, tables, images, and document structure — entirely locally or via Ollama cloud models.

---

## Features

| Feature | Details |
|---------|---------|
| **3-agent CrewAI pipeline** | Document Analyzer → Translator → Quality Checker run on every document |
| **Translation Brief** | Analyzer reads the document once, identifies domain/terms/proper nouns, feeds context to Translator |
| **DOCX translation** | Paragraphs and tables translated; images and inline formatting preserved |
| **Parallel batch processing** | `ThreadPoolExecutor`-based async batching for large documents |
| **Translation quality tiers** | `high` / `medium` / `low` — adjusts the prompt instruction |
| **BLEU / chrF evaluation** | Post-translation quality metrics via [sacrebleu](https://github.com/mjpost/sacrebleu) |
| **UDHR benchmark** | Built-in benchmark against official UN Hindi reference translations |
| **Ollama cloud support** | Use large cloud-hosted models (e.g. `gemma4:31b-cloud`) with no local GPU |

---

## Requirements

- Python 3.10–3.13
- [uv](https://docs.astral.sh/uv/) — fast Python package and environment manager
- [Ollama](https://ollama.com) running locally (routes to cloud models if configured)

---

## Setup

**Linux / macOS:**
```bash
bash ollama_setup.sh
```

**Windows (PowerShell as Administrator):**
```powershell
.\ollama_setup.ps1
```

If you already have `uv` and Ollama installed:
```bash
uv sync
ollama pull gemma4:31b-cloud
```

Add your environment variables to `.env` in the project root:
```env
OLLAMA_API_KEY=your_key_here   # required for cloud models
```

> **Without uv:** `pip install -r requirements.txt` then `python main.py` also works.

---

## Quick Start

1. Place your `.docx` file in the project directory (or set `input_doc` in `config.yaml`)
2. Run:
```bash
uv run python main.py
```
3. Translated document is saved as `translated_paper.docx`

---

## How It Works — Three-Agent Pipeline

```
input.docx
    │
    ▼
DocumentReader              — extracts paragraphs, tables, images, formatting metadata
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  AGENT 1 — Document Structure Analyzer    (runs ONCE)       │
│                                                             │
│  Reads a sample of the document and produces a             │
│  TRANSLATION BRIEF containing:                             │
│    • Document type and domain (academic, legal, religious…) │
│    • Register and tone (formal, scholarly, informal…)       │
│    • Key terms → recommended target-language equivalents    │
│    • Proper nouns → transliterate vs established form       │
│    • Cultural context and consistency guidelines            │
└─────────────────────────────────────────────────────────────┘
    │
    │  Translation Brief injected into every batch below
    │
    ▼
BatchProcessor              — splits paragraphs into batches of 3
    │
    ▼  (per batch)
┌─────────────────────────────────────────────────────────────┐
│  AGENT 2 — Professional Translator                          │
│                                                             │
│  Translates the batch using the Translation Brief as        │
│  context — consistent terminology, correct register,        │
│  proper noun handling.                                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼  (per batch)
┌─────────────────────────────────────────────────────────────┐
│  AGENT 3 — Translation Quality Checker                      │
│                                                             │
│  Reviews the Translator's output — checks meaning           │
│  accuracy, natural language flow, grammar, and              │
│  cultural appropriateness. Refines if needed.               │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
TranslationEvaluator        — optional BLEU / chrF scoring (sacrebleu)
    │
    ▼
DocumentWriter              — writes translations back into the original .docx template
    │
    ▼
translated_paper.docx
```

---

## Configuration

All settings live in `config.yaml`:

```yaml
# Core
target_language: Hindi
input_doc: input.docx
output_doc: translated_paper.docx
llm_model: ollama/gemma4:31b-cloud
translation_quality: high        # high | medium | low
verbose: true                    # show CrewAI agent boxes in terminal

# Document analysis
analysis_sample_size: 15         # paragraphs sampled for Translation Brief

# Batching
batch_size: 3
async_batch: false               # true = parallel batches via ThreadPoolExecutor
max_workers: 3
batch_delay: 1

# Hardware
cuda_device: null
```

### Full configuration reference

| Key | Default | Description |
|-----|---------|-------------|
| `target_language` | `Hindi` | Target translation language |
| `input_doc` | `input.docx` | Source `.docx` path |
| `output_doc` | `translated_paper.docx` | Output `.docx` path |
| `llm_model` | `ollama/gemma4:31b-cloud` | LiteLLM model string |
| `translation_quality` | `high` | Prompt quality instruction tier |
| `verbose` | `true` | Show CrewAI agent execution boxes |
| `analysis_sample_size` | `15` | Paragraphs read by the Document Analyzer |
| `batch_size` | `3` | Paragraphs per translation batch |
| `async_batch` | `false` | Enable parallel batch processing |
| `max_workers` | `3` | Thread count for parallel mode |
| `batch_delay` | `1` | Delay (s) between sequential batches |
| `cuda_device` | `null` | GPU device index |
| `enable_evaluation` | `false` | Run BLEU/chrF after translation |
| `reference_doc` | `null` | Reference translation file path |

---

## Parallel Batch Processing

```yaml
async_batch: true
max_workers: 3
```

Each batch runs in its own thread with an independent `Crew` execution context. Failed batches fall back to the original text without aborting the run.

---

## Quality Evaluation (BLEU / chrF)

```yaml
enable_evaluation: true
reference_doc: references.txt    # one reference translation per paragraph
```

Scores are saved to `evaluation_report.txt`.

| Metric | > 40 / 60 | 20–40 / 40–60 | < 20 / 40 |
|--------|-----------|---------------|-----------|
| BLEU | High quality | Understandable | Low quality |
| chrF | High quality | Acceptable | Needs improvement |

---

## Benchmark

```bash
uv run python benchmark.py              # UDHR corpus, our system only
uv run python benchmark.py --google     # + Google Translate comparison
```

Results saved to `benchmark_report.txt`. Current benchmark result with `gemma4:31b-cloud`:

| Metric | Score | Interpretation |
|--------|-------|---------------|
| BLEU | 60.99 | High quality — approaches human translation |
| chrF | 78.19 | High quality |

---

## Recommended Models

| Model | Ollama tag | RAM needed | Notes |
|-------|-----------|------------|-------|
| **Gemma 4 31B** *(default)* | `gemma4:31b-cloud` | Cloud | Best benchmark score (BLEU 60.99) |
| **Qwen 3.5 397B** | `qwen3.5:cloud` | Cloud (subscription) | Paid Ollama subscription required |
| **Qwen 2.5 14B** | `qwen2.5:14b` | 9 GB local | Best local model for Hindi |
| **Llama 3.3 70B** | `llama3.3:70b` | 48 GB local | Via cloud GPU |
| **Groq free API** | `groq/llama-3.3-70b-versatile` | Cloud (free) | Set `GROQ_API_KEY` in `.env` |

---

## Project Structure

```
.
├── main.py                  # Entry point and summary printer
├── config.py                # Config loader with defaults
├── config.yaml              # User configuration (edit this)
├── agents.py                # All 3 CrewAI agent definitions
├── translation_engine.py    # TranslationEngine (3-agent pipeline + batch processing)
├── translation_system.py    # Workflow orchestrator (read → analyse → translate → write)
├── document_io.py           # DocumentReader and DocumentWriter (DOCX I/O)
├── evaluation.py            # BLEU / chrF evaluation via sacrebleu
├── benchmark.py             # UDHR benchmark
├── utils.py                 # DocumentAnalyzer, PathResolver, TextCleaner
├── pyproject.toml           # uv project manifest
├── requirements.txt         # pip fallback dependency list
├── .env                     # API keys (not committed to git)
├── ollama_setup.sh          # One-step setup (Linux/macOS)
└── ollama_setup.ps1         # One-step setup (Windows)
```

---

## Output Files

| File | Generated by | Contents |
|------|-------------|----------|
| `translated_paper.docx` | `main.py` | Translated document |
| `translation.log` | `main.py` | Full run log |
| `evaluation_report.txt` | `main.py` | BLEU / chrF scores |
| `benchmark_report.txt` | `benchmark.py` | UDHR benchmark with sentence detail |
| `benchmark.log` | `benchmark.py` | Benchmark run log |
| `ollama.log` | Setup scripts | Ollama server output |
