# System Architecture

## 1. Component Overview

### Core Components

1. **CLI (cli.py)**
   - Handles command-line interface
   - Processes arguments and configuration
   - Initializes logging system
   - Orchestrates the conversion process

2. **File System (file_system.py)**
   - Manages file system operations
   - Handles cloud storage paths
   - Creates and manages .cbm directory structure
   - Validates paths and permissions

3. **File Manager (file_manager.py)**
   - Discovers and processes markdown files
   - Manages file queues and processing order
   - Handles file reading and writing operations
   - Coordinates attachment processing

4. **Markdown Processing**
   - **markdown_processor_v2.py**: Core markdown processing logic
   - **markitdown_wrapper.py**: MarkItDown integration and configuration
   - **markdown_file.py**: Markdown file representation and operations
   - **reference_match.py**: Handles Bear attachment references

5. **Conversion System**
   - **converter_factory.py**: Creates appropriate converters
   - **file_converter.py**: Base converter interface
   - **image_converter.py**: Specialized image handling
   - **converters/**: Additional format-specific converters

6. **Image Management**
   - **image_cache.py**: Caches processed images
   - Integrates with GPT-4o for vision processing
   - Handles image format conversions

7. **Logging & Configuration**
   - **logging_config.py**: Centralized logging setup
   - Configurable log levels and output

### 1.1 Configuration Loader

The configuration loader reads settings for consolidate-bear-markdown from a TOML configuration file that specifies:

~~~~
srcDir = "/path/to/bear/markdown"
destDir = "/path/to/output"
logLevel = "INFO"
openai_key = "your-api-key-here"  # Required for GPT-4o image processing
cbm_dir = ".cbm"  # Required for system files and logs
image_analysis_prompt = """  # Optional custom prompt
  Analyze the image and extract all visible text in the original language.
  Reproduce the extracted text in a structured Markdown format, preserving
  any formatting such as headings, bullet points, and highlights.
"""
~~~~

Example cloud paths that are supported:

~~~~
# iCloud Drive
srcDir = "/Users/username/Library/Mobile Documents/com~apple~CloudDocs/BearNotes"
destDir = "/Users/username/Library/Mobile Documents/com~apple~CloudDocs/Consolidated"

# Google Drive
srcDir = "/Users/username/Library/CloudStorage/GoogleDrive-username@gmail.com/My Drive/BearNotes"
destDir = "/Users/username/Library/CloudStorage/GoogleDrive-username@gmail.com/My Drive/Consolidated"
~~~~

This component exposes these settings to the rest of the application through a configuration object.

### 1.2 Environment Management

The project strictly uses UV for all Python environment and package management:

~~~~
# ✅ Correct usage
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv run pytest

# ❌ Forbidden
pip install package
python script.py
python3 -m pytest
~~~~

### 1.3 Main Orchestrator

The core Python application consists of several key operations:

#### 1.3.1 Argument & Config Processing
- Merges command-line arguments with config file settings
- Initializes logging system based on logLevel
- Validates paths and permissions
- Handles cloud storage paths (iCloud, Google Drive) with proper path resolution
- Creates necessary system directories in .cbm

#### 1.3.2 File Discovery
- Walks srcDir to find all .md files
- Handles Bear's export format exactly as-is
- Processes attachments using relative paths from markdown files
- Supports Bear's URL-encoded attachment paths
- Builds processing queue of files and their attachments

#### 1.3.3 Markdown Processing
For each markdown file:
1. Reads source content
2. Identifies attachment references using Bear's format
3. For each attachment:
   ~~~~python
   from markitdown import MarkItDown
   md_conv = MarkItDown(llm_client=client, llm_model="gpt-4o")
   converted = md_conv.convert(attachment_full_path)
   ~~~~
4. Replaces references with converted content
5. Writes final file to destDir

### 1.4 MarkItDown Integration
- Handles conversion of various file types to markdown
- Manages conversion errors with detailed feedback
- Provides consistent output format
- Uses Wand for high-quality SVG to PNG conversion (300 DPI)
- Implements efficient image caching to avoid redundant processing
- Configures OpenAI client for GPT-4o image processing (only permitted vision model)
- Creates informative placeholders for unsupported files

### 1.5 Image Processing
- SVG to PNG conversion using Wand library with 300 DPI quality
- Efficient image caching system in .cbm/cache
- Automatic cache invalidation based on source file changes
- Support for various image formats:
  - SVG → PNG (via Wand)
  - HEIC/HEIF → JPG
  - Standard formats (PNG, JPG, GIF, WebP)
- Detailed error handling for conversion failures

### 1.6 Output Management
- Creates .cbm directory structure:
  ```
  .cbm/
  ├── cache/          # Image and conversion cache
  │   └── images/     # Processed image files
  └── logs/           # System and error logs
  ```
- Maintains Bear's file structure in output
- Handles file write errors with retries
- Ensures all system writes go to .cbm directory
- Provides detailed error messages in output files

### 1.2 File Type Handling

The system uses MarkItDown as the primary converter, with specialized fallbacks when needed:

1. Primary Conversion (MarkItDown):
   - First attempt all conversions through MarkItDown
   - Handles most file types automatically
   - Provides consistent markdown output format
   ~~~~python
   from markitdown import MarkItDown

   markitdown = MarkItDown(llm_client=client, llm_model="gpt-4o")
   result = markitdown.convert(file_path)
   ~~~~

2. Fallback Handlers (only if MarkItDown fails):

   a. Images:
      - SVG → PNG: Wand (300 DPI) when MarkItDown can't process
      - HEIC/HEIF → JPG: Pillow as fallback
      - Standard formats: Direct handling if needed

   b. Documents:
      - PDF: Direct text extraction if MarkItDown fails
      - Spreadsheets: Pandas + tabulate as backup
      - HTML: BeautifulSoup4 if needed

3. Error Strategy:
   - Try MarkItDown first
   - If fails, attempt format-specific fallback
   - Generate detailed error placeholder if all fail
   - Cache successful conversions

### 1.3 Processing Flow

1. For each file:
   ~~~~python
   try:
       # Primary conversion attempt
       result = markitdown.convert(file_path)
       if result.success:
           return format_result(result)

       # Fallback handling if MarkItDown fails
       if file_path.suffix.lower() == '.svg':
           return convert_svg_with_wand(file_path)
       elif file_path.suffix.lower() in ['.heic', '.heif']:
           return convert_heic_with_pillow(file_path)
       # ... other format-specific fallbacks

   except UnsupportedFormatException:
       return create_error_placeholder(file_path)
   ~~~~

## 2. Data Flow

~~~~
 ┌─────────────────────┐       ┌──────────────────────────────┐
 │  config.toml        │       │Bear.app Exported Directory   │
 │  (srcDir/destDir/   │       │  - note1.md                 │
 │   logLevel)         │       │  - note1/ (attachments)      │
 └────────┬────────────┘       │  - note2.md                  │
          │                    │  - note2/ (attachments)      │
          │                    └──────────────────────────────┘
          ▼
 ┌────────────────────────────────┐
 │    Main Orchestrator          │
 │1. Read config                  │
 │2. Setup Logging                │
 │3. Initialize Image Cache       │
 │4. Gather .md files            │
 │5. For each .md:               │
 │   - Parse Bear references     │
 │   - Process attachments       │
 │   - Convert images (Wand)     │
 │   - Cache processed files     │
 │   - Create detailed errors    │
 │   - Write to destDir         │
 └─────────┬─────────────────────┘
           │
           │processed .md + metadata
           ▼
 ┌──────────────────────────────────┐
 │  Output Directory (destDir)     │
 │   - note1.md (with processed    │
 │     content and error details)  │
 │   - note2.md ...                │
 └──────────────────────────────────┘
~~~~

## 3. Technology Stack

1. **Primary Conversion**
   - MarkItDown: Main file conversion library
   - OpenAI GPT-4o: Vision model (used by MarkItDown)

2. **Fallback Libraries**
   - Wand: SVG to PNG conversion when needed
   - Pillow: Image format conversion fallback
   - Pandas: Spreadsheet handling backup
   - BeautifulSoup4: HTML processing fallback

3. **Support Libraries**
   - TOML: Configuration parsing
   - tqdm: Progress tracking
   - urllib: Path handling

4. **Development Tools**
   - pytest: Testing
   - mypy: Type checking
   - black: Formatting
   - ruff: Linting

## 4. Implementation Flow

1. **Setup Phase**
   - Load TOML configuration
   - Initialize MarkItDown with GPT-4o
   - Setup fallback converters
   - Create cache directories

2. **Processing Phase**
   - For each file:
     1. Attempt MarkItDown conversion
     2. If fails, try appropriate fallback
     3. Cache successful results
     4. Generate error placeholders if needed

3. **Error Handling**
   ```markdown
   ## Unsupported Attachment: example.mov

   ### File Details
   - **Type**: MOV
   - **Size**: 1024.50 KB
   - **Modified**: 2024-01-21 13:12:30

   ### Error Information
   - **Primary Error**: MarkItDown conversion failed
   - **Fallback Error**: No suitable converter
   - **Message**: Format not supported

   > Access original file for content
   ```
