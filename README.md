# Consolidate Bear Markdown

A tool to process Bear.app markdown files and their attachments, using GPT-4o for image analysis and MarkItDown for file conversion.

## Features

- Process Bear.app markdown files and inline attachments
- Convert various file types to markdown using MarkItDown
- High-quality SVG to PNG conversion using PyMuPDF
- Analyze images using GPT-4o vision model
- Support for cloud storage paths (iCloud, Google Drive)
- Configurable logging and error handling
- Progress tracking and statistics

## Installation

1. Ensure you have Python 3.11+ installed
2. Install UV package manager if not already installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/consolidate-bear-markdown.git
   cd consolidate-bear-markdown
   ```

4. Create a virtual environment and install dependencies:
   ```bash
   uv venv
   source .venv/bin/activate  # On Unix/macOS
   # or
   .venv\Scripts\activate  # On Windows
   uv pip install -r requirements.txt
   ```

## Configuration

Create a `config.toml` file with the following settings:

```toml
# Required settings
srcDir = "/path/to/bear/notes"      # Source directory containing Bear notes
destDir = "/path/to/output"         # Output directory for processed files
openai_key = "your-openai-api-key"  # OpenAI API key for GPT-4o

# Optional settings
logLevel = "INFO"                   # Logging level (DEBUG, INFO, WARNING, ERROR)
cbm_dir = ".cbm"                    # Directory for system files (default: .cbm)
image_analysis_prompt = """         # Custom prompt for image analysis
    Analyze the image and extract all visible text.
    Preserve formatting and structure in Markdown.
"""
```

## Usage

1. Create your configuration file:
   ```bash
   cp example_config.toml config.toml
   # Edit config.toml with your settings
   ```

2. Run the processor:
   ```bash
   uv run python -m src.cli -c config.toml
   ```

The tool will:
1. Scan the source directory for markdown files
2. Process any attachments found in the files
3. Convert attachments to markdown where possible
4. Convert SVG files to high-quality PNG images
5. Analyze images using GPT-4o
6. Generate processed files in the destination directory
7. Provide statistics on the processing results

## Development

- Run tests:
  ```bash
  uv run pytest -v
  ```

- Run type checking:
  ```bash
  uv run mypy src tests
  ```

## Project Structure

```
consolidate-bear-markdown/
├── .cbm/                  # System files and processing
│   ├── cli.py            # Command-line interface
│   ├── file_system.py    # File system operations
│   ├── logging_config.py # Logging configuration
│   ├── markdown_processor.py # Markdown processing
│   └── markitdown_wrapper.py # MarkItDown integration
├── tests/                 # Test files
├── config.toml           # Configuration file
└── requirements.txt      # Project dependencies
```

## Error Handling

The tool provides detailed error handling:
- File not found errors
- Unsupported file types
- Image processing failures
- SVG conversion issues
- Configuration errors

Errors are logged to `.cbm/consolidate-bear-markdown.log`

## License

MIT License - see LICENSE file for details
