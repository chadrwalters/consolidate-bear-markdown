# Product Requirements Document (PRD)

## 1. Overview

The consolidate-bear-markdown tool processes Markdown files and their associated attachments (exported from Bear.app) and produces inlined Markdown files by invoking the MarkItDown library to convert attachments into Markdown.

A primary use case is processing files directly from cloud storage locations like iCloud Drive or Google Drive, making it seamless to work with Bear.app exports stored in the cloud.

The tool integrates with OpenAI's GPT-4o model by default for enhanced image processing, providing rich descriptions and text extraction from visual content. This enables better accessibility and searchability of image content within the consolidated markdown files. For users who don't need GPT-4o analysis, a --no_image flag is available to skip this step and use simple placeholders instead.

The tool implements smart regeneration, only processing files that have changed since the last run, with an option to force regeneration when needed.

- **Input Directory (srcDir)**: Contains a set of .md files, each possibly having an attachment folder with the same base name as the markdown file.
  - Typically located in cloud storage, e.g., `/Users/<User>/Library/Mobile Documents/com~apple~CloudDocs/BearNotes` for iCloud or a mounted Google Drive path
  - For example, markdown.md might have a folder named markdown that holds attachments like chad.doc, image.svg, etc.
- **Output Directory (destDir)**: The generated .md files will be saved here, with each attachment's content converted to Markdown and inlined within the original file's content.
  - Can also be a cloud storage location, allowing the consolidated files to be immediately available across devices
  - That is, the final markdown.md in the destDir directory will contain the content of each attachment from MarkItDown "in-place," at the correct point in the text.

## 2. Goals and Use Cases

1. **Cloud-First Workflow**: Support direct processing of files from and to cloud storage locations (iCloud Drive, Google Drive) for seamless multi-device access.
2. **Consolidated Markdown**: Users want a single Markdown file that contains the original text plus any attached file's textual representation—helpful for indexing, searching, or further text analysis.
3. **AI-Enhanced Image Processing**: Leverage GPT-4o to provide detailed descriptions of images, extract text from diagrams/charts, and convert visual content into accessible markdown format.
4. **Seamless Integration**: MarkItDown is a convenient library for converting multiple file types. We intend to make use of its flexible capabilities to convert images, .doc/.docx, .pdf, .pptx, .xls/.xlsx, .msg, etc.
5. **Automated Processing**: A user can point the script at a directory, run it, and have the processed, inlined Markdown ready for them.
6. **Efficient Processing**: Only regenerate files when source content has changed, saving time and resources, especially for large attachments and API-based conversions.

## 3. Functional Requirements

### 3.1 Configuration System

The system uses a two-tier configuration approach:

#### 3.1.1 Project Rules (.cursor/rules/)
Modular, portable rule files that can be shared across projects:
```
.cursor/
├── rules/
│   ├── filesystem.rules    # File system organization rules
│   ├── python.rules       # Python coding standards
│   ├── documentation.rules # Documentation requirements
│   ├── git.rules          # Git workflow rules
│   └── ai_commands.rules  # AI-specific procedures
├── config.rules           # Project-specific settings (not in VCS)
└── config.rules.template  # Template for project configuration
```

#### 3.1.2 Project Configuration (.cursor/config.rules)
Project-specific settings that shouldn't be version controlled:
```yaml
config:
    project:
        system_dir: ".cbm"  # Directory for system files
        max_file_lines: 250  # Maximum lines per file
        input_dir: "input"   # Directory for input files
        output_dir: "output" # Directory for output files
        temp_dir: "temp"     # Directory for temporary files
        log_dir: "logs"      # Directory for log files

    # Additional project-specific settings
    # database:
    #     host: "localhost"
    #     port: 5432
```

#### 3.1.3 Legacy config.toml (Deprecated)
The original TOML configuration is maintained for backward compatibility:
```toml
# Required settings
srcDir = "/path/to/bear/markdown"
destDir = "/path/to/output"
openai_key = "your-api-key-here"  # Required for GPT-4o unless --no_image is used
cbm_dir = ".cbm"  # System files location

# Optional settings
logLevel = "WARNING"  # Default: WARNING (for performance metrics)
force_generation = false  # Default: false
no_image = false  # Default: false (can be overridden by --no_image flag)
image_analysis_prompt = """Custom prompt for GPT-4o"""  # Ignored if no_image=true
```

### 3.2 Performance Monitoring
- Comprehensive timing metrics at DEBUG level (moved from WARNING):
  ```
  [DEBUG] Entering function: process_markdown_file
  [DEBUG] Starting block: Processing reference: image.png
  [DEBUG] Starting block: GPT-4o analysis for image.png
  [DEBUG] Finished block: GPT-4o analysis | Elapsed: 2.4321 seconds
  [DEBUG] Finished block: Processing reference | Elapsed: 2.5432 seconds
  [DEBUG] Exiting function: process_markdown_file | Elapsed: 2.6543 seconds
  ```
- Function-level timing via decorators
- Block-level timing via context managers
- Detailed metrics for expensive operations:
  - Image format conversion
  - GPT-4o analysis
  - Cache operations
  - File processing
- Performance statistics in processing summary
- Cache hit/miss rate tracking
- Error timing correlation

### 3.3 File System Management
- All system files stored in `.cbm/` directory:
  ```
  .cbm/
  ├── cache/          # Image and conversion cache
  │   └── images/     # Processed image files
  └── logs/           # System and error logs
  ```
- Support for cloud storage paths (iCloud, Google Drive)
- Robust path validation and permission checks
- Efficient file discovery and queueing
- Smart regeneration based on file modification times

### 3.4 Markdown Processing
- Modular processing pipeline:
  1. File discovery and validation
  2. Change detection and skip logic
  3. Reference extraction and parsing
  4. Attachment processing through MarkItDown
  5. Content consolidation and formatting
- Performance tracking for each pipeline stage
- Specialized handling for Bear's attachment format
- Efficient caching of processed content
- Skip processing for unchanged files

### 3.5 Image Processing
- GPT-4o integration for image analysis
  - Optional processing with --no_image flag
  - Simple placeholder generation when GPT-4o is skipped
  - Placeholder includes image dimensions and file size
  - Tracking of skipped images in processing stats
- Image format conversion support:
  - SVG → PNG via svglib (ReportLab)
  - HEIC/HEIF → JPG
  - Standard formats (PNG, JPG, GIF, WebP)
- Efficient image caching system with performance tracking
- Detailed error handling for conversion failures
- Performance metrics for:
  - Format conversion operations
  - Cache lookups and storage
  - GPT-4o analysis (when not skipped)
  - Overall processing time

### 3.6 Progress Tracking
- TQDM integration for:
  - Overall file processing
  - Individual file attachments
  - Conversion operations
- Detailed progress logging
- Error reporting and recovery
- Performance statistics display:
  ```
  ╭───────────────────── Processing Complete ─────────────────────╮
  │             Processing Summary                               │
  │ ┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┳━━━━━━━┳━━━━━━━━━┓      │
  │ ┃ Category    ┃ Total ┃ Success ┃ Error ┃ Skipped ┃      │
  │ ┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━╇━━━━━━━╇━━━━━━━━━┩      │
  │ │ Files       │    10 │       8 │     1 │       1 │      │
  │ │ Attachments │    25 │      20 │     3 │       2 │      │
  │ │ Images Skip │     5 │      -- │    -- │      -- │      │
  │ └─────────────┴───────┴─────────┴───────┴─────────┘      │
  ╰──────────────────────────────────────────────────────────╯

  Performance Metrics:
  - Total Processing Time: 45.321s
  - Average per File: 4.532s
  - Cache Hit Rate: 85%
  - Slowest Operations:
    - GPT-4o Analysis: 35.123s (or "Skipped" if --no_image used)
    - Image Conversion: 8.765s
    - Cache Operations: 1.433s
  ```

### 3.7 Progress Tracking System
- Nested progress bars using tqdm:
  ```
  Processing Markdown Files: 45%|████▌     | 9/20 [00:25<00:30, 2.75s/file]
    • Processing "Resume.md" ...
    Attachments: 60%|██████    | 3/5 [00:15<00:10, 5.00s/att]
  ```
- Console output levels:
  - WARNING: Default console level for critical messages
  - DEBUG: Detailed timing logs in .cbm/logs/debug.log
- Final summary display:
  ```
  ╭───────────────────── Processing Complete ─────────────────────╮
  │  Category      Total   Success   Error   Skipped             │
  │  Files         20      18        1       1                   │
  │  Attachments   85      80        3       2                   │
  ╰──────────────────────────────────────────────────────────────╯
  ```
- Edge case handling:
  - Zero-attachment files: Shows "(No attachments)" message
  - Error states: Continues progress while logging errors
  - Multiple attachments: Maintains bar clarity with tqdm

## 4. Non-Functional Requirements

1. **Cross-Platform**: The script must run on macOS, Windows, Linux.
2. **Package Management**:
    - All Python package management must be done through UV
    - Direct use of pip or python/python3 commands is forbidden
3. **Robustness**: If an attachment cannot be converted, the script should log a warning and insert a note in the final Markdown.
4. **File System Structure**:
    - All system files must be stored in .cbm directory
    - All logs and processing files must be written to .cbm
5. **Code Organization**:
    - All code files must be less than 250 lines
6. **Testing Requirements**:
    - All tests must run through UV: `uv run pytest -v`
    - Type checking must be performed before tests
    - Tests must run without requiring approval
7. **SVG Processing**:
    - Must use svglib with ReportLab for SVG conversion
    - No other SVG conversion libraries are permitted

## 5. Assumptions & Constraints

- The user has a working Python environment with MarkItDown dependencies installed.
- The user can handle local or cloud-based paths (as long as they are mounted or recognized as standard directories).
- Some attachments may be unsupported by MarkItDown. Those should be skipped, with a fallback message embedded in the final Markdown.
- Vision processing is strictly limited to OpenAI's gpt-4o model; no other vision models are permitted.
