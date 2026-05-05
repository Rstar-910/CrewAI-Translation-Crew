# CrewAI Translation Crew

A multi-agent document translation system built with [CrewAI](https://github.com/joaomdmoura/crewAI) and [Ollama](https://ollama.com). It translates `.docx` files from English to any target language while preserving the original document's formatting, images, and table structures.

---

## Features

- **Multi-agent pipeline** — dedicated agents for translation, quality checking, and document structure analysis
- **Format preservation** — retains bold/italic text, paragraph alignment, headings, and styles from the original document
- **Image preservation** — embedded images are kept in place in the output file
- **Table support** — tables are extracted and carried through the translation pipeline
- **Batch processing** — paragraphs are translated in configurable batches for efficiency
- **Local LLM** — runs entirely on-device via Ollama; no external API keys required
- **YAML configuration** — all settings are controlled from a single `config.yaml` file

---

## Architecture

```
main.py
  └── TranslationSystem          # Orchestrates the full workflow
        ├── DocumentReader        # Reads the .docx and extracts paragraphs, tables, images
        ├── TranslationEngine     # Drives CrewAI crews for each batch
        │     └── AgentFactory   # Creates translator / quality-checker / analyzer agents
        ├── BatchProcessor        # Splits paragraphs into batches and tracks progress
        └── DocumentWriter        # Writes translated content back to a .docx file
```

### Agents

| Agent | Role |
|---|---|
| **Professional Translator** | Translates numbered paragraph batches into the target language |
| **Translation Quality Checker** | Reviews translations for accuracy, flow, and grammar |
| **Document Structure Analyzer** | Ensures document hierarchy and formatting survive translation |

---

## Requirements

- Python 3.9+
- [Ollama](https://ollama.com) installed and running locally
- A `.docx` input file

### Python dependencies

```
crewai
python-docx
pyyaml
```

Install with:

```bash
pip install crewai python-docx pyyaml
```

---

## Ollama Setup

Run the provided setup script to install Ollama and pull the required models:

```bash
bash ollama_setup.sh
```

This installs Ollama, pulls `mistral:7b` (and several alternatives), and starts the Ollama service in the background.

To start Ollama manually at any time:

```bash
ollama serve
```

---

## Configuration

All settings live in `config.yaml`:

```yaml
input_doc: input.docx           # Path to the source .docx file
output_doc: translated_paper.docx  # Path for the translated output file
target_language: Hindi          # Target language for translation
llm_model: ollama/mistral:7b    # Ollama model to use
batch_size: 2                   # Number of paragraphs per translation batch
translation_quality: high       # Quality hint passed to agents
verbose: false                  # Enable verbose CrewAI logging
```

If `config.yaml` is not found, the system creates one automatically with the defaults shown above.

### Supported models

Any model available in your local Ollama installation can be used. To switch models, update `llm_model` in `config.yaml`:

```yaml
llm_model: ollama/llama3.2:3b
```

Pull additional models with:

```bash
ollama pull llama3.2:3b
```

---

## Usage

1. Place your source document in the project directory and name it `input.docx` (or update `input_doc` in `config.yaml`).
2. Set your desired `target_language` in `config.yaml`.
3. Ensure Ollama is running (`ollama serve`).
4. Run:

```bash
python main.py
```

The translated document is saved to the path specified by `output_doc` (default: `translated_paper.docx`).

### Output summary

After a successful run the console prints:

```
TRANSLATION SUMMARY
==================================================
✓ Status: completed
✓ Target Language: Hindi
✓ Output file: translated_paper.docx
✓ Paragraphs translated: 42/42
✓ Tables processed: 3
✓ Images preserved: 5
==================================================
```

A detailed log is also written to `translation.log`.

---

## Project Structure

```
CrewAI-Translation-Crew/
├── main.py               # Entry point
├── translation_system.py # Workflow orchestrator
├── translation_engine.py # CrewAI batch translation engine
├── agents.py             # Agent definitions (translator, QA, analyzer)
├── document_io.py        # DOCX reader and writer tools
├── utils.py              # Document analysis, path resolution, text cleaning
├── config.py             # Configuration loader
├── config.yaml           # User configuration file
├── ollama_setup.sh       # Ollama installation and model pull script
└── input.docx            # Sample input document
```

---

## How It Works

1. **Read** — `DocumentReader` opens the `.docx` file and extracts every paragraph (with formatting metadata), all tables, and all embedded images.
2. **Batch translate** — `BatchProcessor` groups paragraphs into batches. For each batch, `TranslationEngine` builds a CrewAI `Crew` with a `Professional Translator` agent and runs it via `crew.kickoff()`.
3. **Parse & align** — `TextCleaner` strips model preamble from the result. Translated paragraphs are re-aligned with the original paragraph list so empty paragraphs and image-only paragraphs are preserved unchanged.
4. **Write** — `DocumentWriter` opens the original file as a template, replaces text runs in-place (leaving image runs untouched), and saves the output document.

---

## Logging

Runtime logs are written to both the console and `translation.log`. Set `verbose: true` in `config.yaml` to enable detailed CrewAI agent output.

---

## License

This project is provided as-is for educational and research purposes.