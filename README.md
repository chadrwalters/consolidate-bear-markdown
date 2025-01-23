# Consolidate Bear Markdown

This repository provides a Python-based tool to process Markdown files exported from the [Bear](https://bear.app/) note-taking application. The tool can read each Markdown note along with its attachments and generate a single, consolidated Markdown file. Attachments are converted to Markdown using the MarkItDown library (with additional AI-driven image analysis using GPT-4o).

The project is well-suited for users who want to keep Bear's structure — a Markdown file and a folder of attachments — but merge them into a single, self-contained, and more portable Markdown file.

## Features

- Converts various attachment formats (images, office documents, PDFs, etc.) to a Markdown-friendly format with MarkItDown.
- Inlines image content by providing accessible descriptions and extracted text (using GPT-4o for vision analysis).
- Maintains your file structure in the output, preserving any text layout or references.
- Automatically detects changed files and only re-processes those (with a force-run option available).
- Generates performance metrics and logs for each step of the conversion process.
- Offers progress bars and summary statistics to keep track of processed notes.

## Project Structure

Some key files and directories:

- `src/`: Contains the core Python modules, including:
  - `cli.py`: Command-line interface that runs the tool.
  - `file_system.py`, `file_manager.py`, `markdown_processor_v2.py`: Handle file discovery, attachment management, and the main logic for converting and consolidating Markdown content.
  - `converters/`: Collection of format-specific converters (e.g., `image_converter.py`, `document_converter.py`, `spreadsheet_converter.py`).
  - `markitdown.py`: Example integration of a Pandoc-based system for converting documents to Markdown.
- `tests/`: Contains pytest-based test suites that validate functionality and integration.
- `docs/`: Contains project documentation, including a PRD and architectural overview.
- `.cbm/`: Default directory (created at runtime) for caching, logs, and other system files.

## Requirements

1. Python 3.11+
2. Pandoc installed (for converting document formats).
3. Valid OpenAI API Key if you need GPT-4o vision analysis (set in the configuration).
4. All Python environment management and commands must be run through the [UV](https://github.com/charliermarsh/ruff) CLI to comply with this repo's policy (no direct `pip install`, no direct `python` invocations).

## Installation & Setup

1. Clone this repo:
   ```bash
   git clone https://github.com/YourUsername/consolidate-bear-markdown.git
   cd consolidate-bear-markdown
   ```

2. Create a Python virtual environment and install dependencies.
   Make sure to use UV:
   ```bash
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

3. (Optional but Recommended) Copy `example_config.toml` to a file named `config.toml` and update it:
   ```bash
   cp example_config.toml config.toml
   ```
   Then open `config.toml` in your editor and set:
   - `srcDir` and `destDir` to the paths containing your Bear notes and the output location.
   - `openai_key` to your OpenAI API key if GPT-4o analysis is required.

## Usage

From within your virtual environment, run the CLI script via UV using the Python module syntax:

```bash
uv run python -m src.cli --config config.toml
```

Key options:
- `--force`: Ignoring modification times, reprocess all files
- `--config <path>`: Use a specific TOML configuration file (defaults to config.toml if not provided)

Example:
```bash
uv run python -m src.cli --config config.toml --force
```
This converts all Markdown files in srcDir to the output directory, inlining attachments and performing GPT-4o analysis for images.

## Logs, Caching, & System Files

By default, system files go to `.cbm` in the repo or working directory:
- `.cbm/cache` for storing cached conversions
- `.cbm/logs` for logs

This ensures no clutter in your source or destination directories.

## Testing

Use UV to run all tests:
```bash
uv run pytest -v
```

This will:
- Conduct type checking (via mypy)
- Run linting (via ruff)
- Execute tests (via pytest)

## Contributing

- Follow the repository rules: All code must remain under 250 lines, all environment commands via UV, etc.
- Submit pull requests or open issues for improvements or bug fixes.

## License

Distributed under the [MIT License](LICENSE).

---

Enjoy consolidating your Bear notes with inlined attachments and AI-augmented images!
