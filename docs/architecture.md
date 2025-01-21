# System Architecture

## 1. Component Overview

### 1.1 Configuration Loader

The configuration loader reads settings for consolidate-bear-markdown from a configuration file (TOML/YAML/INI) that specifies:

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

Example cloud paths that should be supported:

~~~~
# iCloud Drive
srcDir = "/Users/username/Library/Mobile Documents/com~apple~CloudDocs/BearNotes"
destDir = "/Users/username/Library/Mobile Documents/com~apple~CloudDocs/Consolidated"

# Google Drive
srcDir = "/Users/username/Google Drive/My Drive/BearNotes"
destDir = "/Users/username/Google Drive/My Drive/Consolidated"
~~~~

This component exposes these settings to the rest of the application through a configuration object.

### 1.2 Environment Management

The project strictly uses UV for all Python environment and package management. Direct use of pip or python/python3 commands is forbidden:

~~~~
uv create myenv
uv activate myenv
uv install markitdown tqdm pytest mypy  # Include testing dependencies
~~~~

### 1.3 Main Orchestrator

The core Python application consists of several key operations:

#### 1.3.1 Argument & Config Processing
- Merges command-line arguments with config file settings
- Initializes logging system based on logLevel
- Validates paths and permissions
- Handles cloud storage paths (iCloud, Google Drive) with proper path resolution

#### 1.3.2 File Discovery
- Walks srcDir to find all .md files
- For each .md file, checks for corresponding attachment folder
- Builds processing queue of files and their attachments

#### 1.3.3 Markdown Processing
For each markdown file:
1. Reads source content
2. Identifies attachment references
3. For each attachment:
   ~~~~python
   from markitdown import MarkItDown
   md_conv = MarkItDown()
   converted = md_conv.convert(attachment_full_path)
   ~~~~
4. Replaces references with converted content
5. Writes final file to destDir

### 1.4 MarkItDown Integration
- Handles conversion of various file types to markdown
- Manages conversion errors and fallbacks
- Provides consistent output format
- Uses Wand for high-quality SVG to PNG conversion
- Implements efficient image caching to avoid redundant processing
- Configures OpenAI client for GPT-4o image processing (only permitted vision model):
  ~~~~python
  from openai import OpenAI
  client = OpenAI()
  md = MarkItDown(llm_client=client, llm_model="gpt-4o")
  ~~~~

### 1.5 Image Processing
- SVG to PNG conversion using Wand library
- Image caching system to store processed images
- Configurable cache directory within .cbm
- Automatic cache invalidation based on source file changes
- Support for various image formats (SVG, PNG, JPG, etc.)

### 1.6 Output Management
- Creates .cbm directory for system files and logs
- Creates destDir if needed
- Maintains file naming consistency
- Handles file write errors
- Ensures all system writes go to .cbm directory

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
 │      (Python program)         │
 │1. Read config                  │
 │2. Setup Logging                │
 │3. Initialize Image Cache       │
 │4. Gather .md files            │
 │5. For each .md:               │
 │   - detect references         │
 │   - MarkItDown attachments    │
 │   - Process images (Wand)     │
 │   - inline output             │
 │   - Write new .md to destDir  │
 └─────────┬─────────────────────┘
           │
           │converted/inlined .md
           ▼
 ┌──────────────────────────────────┐
 │  Output Directory (destDir)     │
 │   - note1.md (with inlined      │
 │     content for attachments)    │
 │   - note2.md ...                │
 └──────────────────────────────────┘
~~~~

## 3. Technology Stack

1. **Core Technologies**
   - Python 3.x
   - UV for environment management
   - MarkItDown library
   - OpenAI GPT-4o for image analysis
   - Wand for image processing

2. **Key Dependencies**
   - Wand for SVG/image conversion
   - tqdm for progress indication
   - Standard library components (os, pathlib, logging)
   - Configuration parser (TOML/YAML)

## 4. Implementation Flow

1. **Setup**
   - User configures config.toml
   - Environment created with UV (no direct pip/python usage)
   - Dependencies installed via UV

2. **Execution**
   - Script invoked with config path
   - Type checking performed
   - Tests run via `uv run pytest -v`
   - Files processed with progress indication
   - Output generated to destDir

3. **Error Handling**
   - Logging at configured level
   - Graceful fallbacks for conversion failures
   - Clear error messages in output files
