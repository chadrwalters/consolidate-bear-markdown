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

### 1.1 Configuration System

The configuration system is split into two main parts:

#### 1.1.1 Rules System (.cursor/rules/)
Modular, portable rules that define project standards and procedures:
```python
class RulesManager:
    def __init__(self, rules_dir: Path = Path(".cursor/rules")):
        self.rules_dir = rules_dir
        self.rules: Dict[str, Dict] = {}
        self._load_rules()

    def _load_rules(self) -> None:
        """Load all .rules files from the rules directory."""
        for rule_file in self.rules_dir.glob("*.rules"):
            self.rules[rule_file.stem] = self._parse_rule_file(rule_file)

    def get_rule(self, rule_type: str, rule_name: str) -> Any:
        """Get a specific rule by type and name."""
        return self.rules.get(rule_type, {}).get(rule_name)
```

#### 1.1.2 Project Configuration (.cursor/config.rules)
Project-specific settings that reference the rules:
```python
class ConfigManager:
    def __init__(self, config_path: Path = Path(".cursor/config.rules")):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load project-specific configuration."""
        if not self.config_path.exists():
            self._create_from_template()
        self.config = self._parse_config_file()

    def get_setting(self, section: str, key: str) -> Any:
        """Get a specific configuration value."""
        return self.config.get(section, {}).get(key)

    def _create_from_template(self) -> None:
        """Create config.rules from template if it doesn't exist."""
        template_path = self.config_path.parent / "config.rules.template"
        if template_path.exists():
            shutil.copy(template_path, self.config_path)
```

#### 1.1.3 Configuration Integration
The system integrates both components:
```python
class Configuration:
    def __init__(self):
        self.rules_manager = RulesManager()
        self.config_manager = ConfigManager()

    def get_system_dir(self) -> Path:
        """Get configured system directory."""
        return Path(self.config_manager.get_setting("project", "system_dir"))

    def get_max_file_lines(self) -> int:
        """Get configured maximum file lines."""
        return self.config_manager.get_setting("project", "max_file_lines")

    def should_process_file(self, file_path: Path) -> bool:
        """Check if file should be processed based on rules."""
        file_rules = self.rules_manager.get_rule("filesystem", "file_size")
        max_lines = self.get_max_file_lines()
        return self._check_file_rules(file_path, file_rules, max_lines)
```

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
  - File counts:
    - Processed: Files successfully handled
    - Errors: Files with processing failures
    - Skipped: Files intentionally skipped
    - Unchanged: Files not needing updates
  - Attachment counts:
    - Total: Local attachments found
    - Processed: Successfully converted
    - Errors: Failed to process
    - Skipped: Intentionally skipped
    - External URLs: References to external content (tracked separately)
  - Operation timing metrics
  - Cache hit/miss rates
  - Performance bottlenecks

The statistics system distinguishes between local attachments and external URLs:
```python
@dataclass
class ProcessingStats:
    # File statistics
    files_processed: int = 0
    files_errored: int = 0
    files_skipped: int = 0
    files_unchanged: int = 0

    # Attachment statistics
    total_attachments: int = 0     # Local attachments only
    success_attachments: int = 0
    error_attachments: int = 0
    skipped_attachments: int = 0
    external_urls: int = 0         # Tracked separately

    def record_external_url(self) -> None:
        """Record an external URL reference without affecting attachment counts."""
        self.external_urls += 1
```

This separation ensures accurate tracking of:
- Local attachments that need processing
- External URLs that are intentionally skipped
- True error rates for local content

The final summary displays this distinction:
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

### 1.8 Progress Tracking System

The progress tracking system is implemented through several components:

1. **Progress Manager (progress_manager.py)**
   ```python
   class ProgressManager:
       def __init__(self):
           self.file_progress: Optional[tqdm] = None
           self.attachment_progress: Optional[tqdm] = None

       def start_file_progress(self, total_files: int) -> None:
           self.file_progress = tqdm(total=total_files, desc="Processing Markdown Files")

       def start_attachment_progress(self, total_attachments: int) -> None:
           self.attachment_progress = tqdm(total=total_attachments, desc="Processing Attachments")
   ```

2. **Console Manager (console_manager.py)**
   ```python
   class ConsoleManager:
       def __init__(self, log_level: str = "WARNING"):
           self.log_level = log_level
           self.setup_logging()

       def setup_logging(self) -> None:
           # Configure console logging
           console_handler = logging.StreamHandler()
           console_handler.setLevel(self.log_level)

           # Configure file logging
           file_handler = logging.FileHandler(".cbm/logs/debug.log")
           file_handler.setLevel(logging.DEBUG)
   ```

3. **Statistics Tracking**
   ```python
   class ProcessingStats:
       def __init__(self):
           self.total_files: int = 0
           self.processed_files: int = 0
           self.error_files: int = 0
           self.skipped_files: int = 0
           self.unchanged_files: int = 0
           self.total_attachments: int = 0
           self.processed_attachments: int = 0
           self.error_attachments: int = 0
           self.skipped_attachments: int = 0
   ```

4. **Integration in MarkdownProcessorV2**
   ```python
   class MarkdownProcessorV2:
       def __init__(self):
           self.progress_manager = ProgressManager()
           self.console_manager = ConsoleManager()
           self.stats = ProcessingStats()

       def process_all(self) -> None:
           markdown_files = self.file_system.discover_markdown_files()
           self.progress_manager.start_file_progress(len(markdown_files))

           for md_file in markdown_files:
               self.process_markdown_file(md_file)
               self.progress_manager.update_file_progress()

           self.print_summary()
   ```

Key features of the progress tracking system:
- Nested progress bars for files and attachments
- Real-time status updates with tqdm
- Detailed timing information via logging
- Error reporting and statistics collection
- Clear console output with WARNING-level messages
- Comprehensive DEBUG logs in `.cbm/logs/debug.log`
- Final summary table with processing statistics

The system ensures users have clear visibility into:
- Overall progress of the conversion process
- Current file being processed
- Attachment processing progress
- Error states and warnings
- Final processing statistics

## 2. Data Flow [UPDATED v2]

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
 │2. Setup Logging & Progress     │ [NEW v2]
 │3. Initialize Image Cache       │
 │4. Gather .md files            │
 │5. For each .md:               │
 │   - Show outer progress bar   │ [NEW v2]
 │   - Parse Bear references     │
 │   - Show inner progress bar   │ [NEW v2]
 │   - Process attachments       │
 │   - Convert images (Wand)     │
 │   - Cache processed files     │
 │   - Create detailed errors    │
 │   - Write to destDir         │
 │6. Display final summary       │ [NEW v2]
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
