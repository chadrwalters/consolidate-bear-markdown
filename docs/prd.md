# Product Requirements Document (PRD)

## 1. Overview

The consolidate-bear-markdown tool processes Markdown files and their associated attachments (exported from Bear.app) and produces inlined Markdown files by invoking the MarkItDown library to convert attachments into Markdown.

A primary use case is processing files directly from cloud storage locations like iCloud Drive or Google Drive, making it seamless to work with Bear.app exports stored in the cloud.

The tool integrates with OpenAI's GPT-4o model by default for enhanced image processing, providing rich descriptions and text extraction from visual content. This enables better accessibility and searchability of image content within the consolidated markdown files.

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

## 3. Functional Requirements

### 3.1 Config File
- Must specify inputDir (the Bear-app-exported notes location) and outputDir (the location of resulting processed .md files).
- Both directories might be located in an iCloud Drive or Google Drive folder. The script should handle that seamlessly, so paths like /Users/<User>/Library/Mobile Documents/com~apple~CloudDocs/... or a mounted Google Drive path are supported.
- OpenAI API key configuration for GPT-4o image processing
- Optional: Custom prompts for image analysis

### 3.2 Reading Source Markdown
- For each .md file in inputDir, detect if a corresponding folder (with the same base name) exists (e.g. markdown.md and folder markdown/).
- When attachments are referenced in the .md file (e.g. ![some-file](markdown/some-file.doc)), replace those references with the MarkItDown output inlined in the final text.

### 3.3 Attachment Conversion
- If an attachment is present (e.g. chad.doc or image.svg):
  - Call MarkItDown's .convert() method on the attachment to produce its Markdown text.
  - Insert that output in the place of the attachment reference in the final .md file (with a small separator or heading).
- For image files:
  - Use GPT-4o to analyze and describe image content
  - Extract any visible text from diagrams, charts, or screenshots
  - Convert visual information into structured markdown format
  - Preserve original image reference while adding the AI-generated description

### 3.4 TQDM Progress
- When processing multiple Markdown files, display a TQDM progress bar or stats (e.g., "Processing 5 files…").
- Optionally, within each file, also show progress for attachments (if many exist).

### 3.5 Logging / Verbose Levels
- Use Python's logging or a similar approach to differentiate standard progress logs (INFO) vs. debug details (DEBUG).
- The user can control the logging level in the config file to get more or less detail while processing.

### 3.6 Output
- For every .md file, produce a new (or overwrite existing) .md in the output directory with inlined attachment text.
- The final structure in the destDir will just be .md files (no subfolders for attachments).

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

## 5. Assumptions & Constraints

- The user has a working Python environment with MarkItDown dependencies installed.
- The user can handle local or cloud-based paths (as long as they are mounted or recognized as standard directories).
- Some attachments may be unsupported by MarkItDown. Those should be skipped, with a fallback message embedded in the final Markdown.
- Vision processing is strictly limited to OpenAI's gpt-4o model; no other vision models are permitted.
