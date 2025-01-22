# System Architecture

## 1. Component Overview

### Core Components

1. **CLI (cli.py)**
   - Handles command-line interface
   - Processes arguments and configuration
   - Initializes logging system
   - Orchestrates the conversion process
   - Handles force regeneration flag

2. **File System (file_system.py)**
   - Manages file system operations
   - Handles cloud storage paths
   - Creates and manages .cbm directory structure
   - Validates paths and permissions
   - Provides file modification time utilities

3. **File Manager (file_manager.py)**
   - Discovers and processes markdown files
   - Manages file queues and processing order
   - Handles file reading and writing operations
   - Coordinates attachment processing
   - Implements change detection logic

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
openai_key = "your-api-key-here"  # Required for GPT-4o
cbm_dir = ".cbm"  # Required for system files and logs
force_generation = false  # Optional, default false
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

#### 1.3.1 Performance Logging
- Comprehensive timing metrics at WARNING level for:
  - Function-level timing via `@log_timing` decorator
  - Block-level timing via `log_block_timing` context manager
  - Entry/exit timestamps for key functions
  - Detailed timing for expensive operations:
    - Image format conversion
    - GPT-4o analysis
    - Cache operations
    - File processing
- All timing logs include:
  - Operation name/description
  - Start time
  - End time
  - Total elapsed time in seconds
  - Error tracking with timing context

#### 1.3.2 Argument & Config Processing
- Merges command-line arguments with config file settings
- Initializes logging system based on logLevel
- Validates paths and permissions
- Handles cloud storage paths (iCloud, Google Drive) with proper path resolution
- Creates necessary system directories in .cbm
- Processes force regeneration flag

#### 1.3.3 File Discovery and Change Detection
- Walks srcDir to find all .md files
- Handles Bear's export format exactly as-is
- Processes attachments using relative paths from markdown files
- Supports Bear's URL-encoded attachment paths
- Checks file modification times for smart regeneration
- Builds processing queue of files and their attachments

#### 1.3.4 Markdown Processing
For each markdown file:
1. Check if processing is needed:
   ```python
   def should_process(md_file: MarkdownFile) -> bool:
       if force_generation:
           return True

       output_path = dest_dir / md_file.relative_path
       if not output_path.exists():
           return True

       output_mtime = output_path.stat().st_mtime
       if md_file.mtime > output_mtime:
           return True

       for attachment in md_file.attachments:
           if attachment.mtime > output_mtime:
               return True

       return False
   ```
2. If processing needed:
   - Reads source content
   - Identifies attachment references using Bear's format
   - For each attachment:
     ```python
     from markitdown import MarkItDown
     md_conv = MarkItDown(llm_client=client, llm_model="gpt-4o")
     converted = md_conv.convert(attachment_full_path)
     ```
   - Replaces references with converted content
   - Writes final file to destDir
3. If processing not needed:
   - Log skip at INFO level
   - Update skip counter in statistics

### 1.4 MarkItDown Integration
- Handles conversion of various file types to markdown
- Manages conversion errors with detailed feedback
- Provides consistent output format
- Uses svglib with ReportLab for SVG to PNG conversion
- Implements efficient image caching to avoid redundant processing
- Configures OpenAI client for GPT-4o image processing (only permitted vision model)
- Creates informative placeholders for unsupported files
- Performance tracking for all conversion operations

### 1.5 Image Processing
- SVG to PNG conversion using svglib with ReportLab
- Efficient image caching system in .cbm/cache
- Automatic cache invalidation based on source file changes
- Support for various image formats:
  - SVG → PNG (via svglib)
  - HEIC/HEIF → JPG
  - Standard formats (PNG, JPG, GIF, WebP)
- Detailed error handling for conversion failures
- Performance metrics for:
  - Format conversion operations
  - Cache lookups and storage
  - GPT-4o analysis
  - Overall processing time

### 1.6 Output Management
- Creates .cbm directory structure:
  ```
  .cbm/
  ├── cache/          # Image and conversion cache
  │   └── images/     # Processed image files
  └── logs/          # System, error, and performance logs
  ```
- Maintains Bear's file structure in output
- Handles file write errors with retries
- Ensures all system writes go to .cbm directory
- Provides detailed error messages in output files
- Tracks processing statistics including:
  - File counts (processed/skipped/errors)
  - Operation timing metrics
  - Cache hit/miss rates
  - Performance bottlenecks

### 1.7 Change Detection System

The change detection system is implemented across several components:

1. **Configuration**
   ```python
   class Config:
       force_generation: bool = False

       @classmethod
       def from_toml(cls, config_path: Path) -> Config:
           config = cls()
           toml_config = toml.load(config_path)
           config.force_generation = toml_config.get("force_generation", False)
           return config
   ```

2. **CLI Integration**
   ```python
   def parse_args() -> argparse.Namespace:
       parser = argparse.ArgumentParser()
       parser.add_argument("--force", action="store_true",
                         help="Force regeneration of all files")
       return parser.parse_args()
   ```

3. **File Manager**
   ```python
   class FileManager:
       def __init__(self, config: Config):
           self.force_generation = config.force_generation

       def should_process(self, md_file: MarkdownFile) -> bool:
           if self.force_generation:
               return True

           output_path = self.get_output_path(md_file)
           if not output_path.exists():
               return True

           return self._check_modifications(md_file, output_path)

       def _check_modifications(
           self, md_file: MarkdownFile, output_path: Path
       ) -> bool:
           output_mtime = output_path.stat().st_mtime

           # Check markdown file
           if md_file.mtime > output_mtime:
               return True

           # Check attachments
           for attachment in md_file.attachments:
               if attachment.mtime > output_mtime:
                   return True

           return False
   ```

4. **Statistics Tracking**
   ```python
   @dataclass
   class ProcessingStats:
       files_processed: int = 0
       files_skipped: int = 0
       files_errored: int = 0
       success: int = 0
       error: int = 0
       missing: int = 0
       errors: List[str] = field(default_factory=list)

       def update_skip(self) -> None:
           self.files_skipped += 1
   ```

This architecture ensures efficient processing by only regenerating files when necessary while maintaining flexibility through the force regeneration option.

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
