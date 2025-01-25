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
- Provides nested progress tracking:
  - Outer progress bar for total Markdown files
  - Inner progress bar for attachments within each file
  - Clear console output with WARNING-level messages
  - Detailed DEBUG logs in `.cbm/logs/debug.log`
  - Comprehensive final summary table
- Optional GPT-4o vision analysis with --no_image flag to skip when not needed.

## Progress Tracking [NEW v2]

The tool provides clear progress feedback during processing:

```
Processing Markdown Files: 45%|████▌     | 9/20 [00:25<00:30, 2.75s/file]
  • Processing "Resume.md" ...
  Attachments: 60%|██████    | 3/5 [00:15<00:10, 5.00s/att]
```

When processing completes, you'll see a detailed summary:

```
─────────────────────────────────────────────────
                Processing Summary
────────────────────┬────────────────────────────
 Files              │ Attachments
────────────────────┼────────────────────────────
 Total:       41   │ Total:       54
 Processed:   41   │ Processed:   54
 Errors:       0   │ Errors:       0
 Skipped:      0   │ Skipped:      0
 Unchanged:    0   │ External:    52
─────────────────────────────────────────────────
```

The summary distinguishes between:
- **Files**: Markdown documents being processed
  - Total: All markdown files found
  - Processed: Successfully handled files
  - Errors: Files with processing failures
  - Skipped: Files intentionally skipped
  - Unchanged: Files not needing updates
- **Attachments**: Local files and external references
  - Total: Number of local attachments found
  - Processed: Successfully converted attachments
  - Errors: Failed conversions
  - Skipped: Intentionally skipped local files
  - External: Count of external URL references (tracked separately)
  - Images Skipped: Number of images skipped due to --no_image flag

## Project Structure

Some key files and directories:

- `src/`: Contains the core Python modules, including:
  - `cli.py`: Command-line interface that runs the tool.
  - `file_system.py`, `file_manager.py`, `markdown_processor_v2.py`: Handle file discovery, attachment management, and the main logic for converting and consolidating Markdown content.
  - `converters/`: Collection of format-specific converters (e.g., `image_converter.py`, `document_converter.py`, `spreadsheet_converter.py`).
  - `markitdown.py`: Example integration of a Pandoc-based system for converting documents to Markdown.
- `tests/`: Contains pytest-based test suites that validate functionality and integration.
- `docs/`: Contains project documentation, including a PRD and architectural overview.
- `.cursor/`: Contains project-specific rules and configuration:
  - `rules/`: Directory containing modular rule files
    - `filesystem.rules`: File system and organization rules
    - `python.rules`: Python coding standards
    - `documentation.rules`: Documentation requirements
    - `git.rules`: Git workflow rules
    - `ai_commands.rules`: AI-specific commands and procedures
  - `config.rules`: Project-specific configuration (not checked into version control)
  - `config.rules.template`: Template for project configuration
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
- `--no_image`: Skip GPT-4o vision analysis for images, replacing with a simple placeholder

Example:
```bash
# Process all files with GPT-4o vision analysis
uv run python -m src.cli --config config.toml --force

# Process files but skip GPT-4o vision analysis
uv run python -m src.cli --config config.toml --no_image
```

When using --no_image, images will still be processed but instead of GPT-4o analysis, you'll get a simple placeholder with image dimensions and file size. This is useful when:
- You want faster processing without waiting for GPT-4o analysis
- You want to save on OpenAI API costs
- You don't need detailed image descriptions
- You're doing a quick test run or debugging

## Logs, Caching, & System Files

The system uses two main directories for configuration and system files:

1. `.cursor/`: Contains project rules and configuration
   - Rules are modular and portable across projects
   - Project-specific settings in `config.rules` (not version controlled)
   - Template provided in `config.rules.template`

2. `.cbm/`: Contains runtime files and logs (as configured in `.cursor/config.rules`):
   - `.cbm/cache` for storing cached conversions
   - `.cbm/logs` for logs
   - Additional directories as specified in configuration

This ensures:
- Portable rules that can be reused across projects
- Project-specific configuration separate from shared rules
- No clutter in your source or destination directories
- Configurable system file locations

## Testing

Use UV to run all tests:
```
