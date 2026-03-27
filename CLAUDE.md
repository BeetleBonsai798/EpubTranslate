# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EpubTranslateProd is a PySide6 desktop application that translates EPUB books using LLM APIs (OpenRouter or custom OpenAI-compatible endpoints). It converts EPUB chapters to Markdown, chunks them by token count, sends them to an LLM for translation, and reassembles the translated content back into an EPUB.

## Setup & Installation

```bash
pip install -r requirements.txt
# or
pip install -e .
```

Requires Python >= 3.9 and a system installation of Pandoc (used via pypandoc for HTML/Markdown conversion).

Configuration: copy `.env.example` to `.env` and `translator_config.json.example` to `translator_config.json`.

Entry point: `python main.py` (also installable as `epub-translate` console script).

## Architecture

**Threading model**: `TranslationWorker` instances are `QObject`s moved to `QThread`s. Multiple concurrent workers pull from a shared `queue.Queue`. All UI updates happen via Qt signals back to the main thread. Concurrency must be 1 when context mode is enabled.

**Translation pipeline per chapter**:
1. SVG preprocessing (BeautifulSoup) → HTML to Markdown (pypandoc) → token-based chunking (tiktoken, `cl100k_base`)
2. Each chunk: build LLM message list (system prompt + context + previous chapters + text) → call OpenAI-compatible API with provider retry logic → parse JSON response
3. Extract `complete_translation`, `characters`, `places`, `terms`, `notes`, `toc_entries` from response → update `ContextManager` (persisted to disk as JSON)
4. Reassemble chunks → Markdown to XHTML (pypandoc) → write to `{output}/xhtml/{n}.xhtml`

**Final build**: `EpubRebuilder` loads the original EPUB, injects translated XHTMLs, and `TocTranslationWorker` translates the table of contents in batches.

## Key Modules

- `src/translator/core/translation_worker.py` — Core translation engine. Handles chunking, LLM API calls with provider failover, JSON response parsing, and context extraction.
- `src/translator/core/context_manager.py` — Persists characters/places/terms/notes as JSON databases in `{output}/context/`. Generates context prompts injected into LLM messages.
- `src/translator/core/context_filter.py` — Relevance-based filtering of context entries for the current chunk. Handles CJK-specific matching (hiragana/katakana normalization).
- `src/translator/core/prompts.py` — Loads prompt templates from `prompts_config.json` at import time.
- `src/translator/ui/main_window.py` — Entire GUI (~1940 lines). Left panel: settings. Right panel: tabbed output (per-worker logs, chapter overview, context databases, raw JSON).
- `src/translator/core/epub_rebuilder.py` — Constructs final translated EPUB using ebooklib.
- `src/translator/config/config_manager.py` — Reads/writes `translator_config.json` and `.env`. Separates secrets from settings.
- `src/translator/api/openrouter_fetcher.py` — Background QThread fetching available models/providers from OpenRouter API.

## Configuration Files

- `.env` — API keys (`OPENROUTER_API_KEY`, `CUSTOM_ENDPOINT_URL`, `CUSTOM_ENDPOINT_KEY`). Git-ignored.
- `translator_config.json` — All runtime settings (model, tokens, temperature, providers, window geometry). Git-ignored.
- `prompts_config.json` — LLM system prompt and instruction templates. Git-tracked and rarely edited.

## Output Structure

Translations are written to `{epub_name}_translated/` at the project root:
- `xhtml/{n}.xhtml` — Translated chapter files
- `context/{epub_name}_{characters,places,terms,notes}.json` — Persistent context databases
- `last_session.json` — Resume support

## Notes

- No test suite exists.
- The LLM is instructed to return strict JSON containing both the translation and extracted context entities. The `_build_instruction()` method in `translation_worker.py` dynamically assembles the expected JSON schema.
- `prompts_config.json` controls the base prompt position (before/after context) and all instruction text.