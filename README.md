# 🚀 Yai 💬 - AI powered terminal assistant

[![build](https://github.com/ekkinox/yai/actions/workflows/build.yml/badge.svg)](https://github.com/ekkinox/yai/actions/workflows/build.yml)
[![release](https://github.com/ekkinox/yai/actions/workflows/release.yml/badge.svg)](https://github.com/ekkinox/yai/actions/workflows/release.yml)
[![doc](https://github.com/ekkinox/yai/actions/workflows/doc.yml/badge.svg)](https://github.com/ekkinox/yai/actions/workflows/doc.yml)

> Unleash the power of artificial intelligence to streamline your command line experience.

![Intro](docs/_assets/intro.gif)

## What is Yai ?

`Yai` (your AI) is an assistant for your terminal, using [OpenAI ChatGPT](https://chat.openai.com/) to build and run commands for you. You just need to describe them in your everyday language, it will take care or the rest.

You have any questions on random topics in mind? You can also ask `Yai`, and get the power of AI without leaving `/home`.

It is already aware of your:
- operating system & distribution
- username, shell & home directory
- preferred editor

And you can also give any supplementary preferences to fine tune your experience.

## Documentation

A complete documentation is available at [https://ekkinox.github.io/yai/](https://ekkinox.github.io/yai/).

## Quick start

To install `Yai`, simply run:

```shell
curl -sS https://raw.githubusercontent.com/ekkinox/yai/main/install.sh | bash
```

At first run, it will ask you for an [OpenAI API key](https://platform.openai.com/account/api-keys), and use it to create the configuration file in `~/.config/yai.json`.

See [documentation](https://ekkinox.github.io/yai/getting-started/#configuration) for more information.

## Thanks

Thanks to [@K-arch27](https://github.com/K-arch27) for the `yai` name idea!

## Features

- Processes Bear.app exported Markdown files and attachments
- Integrates with OpenAI's GPT-4o model for enhanced image processing
- Supports cloud storage locations (iCloud Drive, Google Drive)
- Smart regeneration - only processes files that have changed
- Force regeneration option available when needed
- Simple SVG to PNG conversion using svglib with ReportLab

## Configuration

Example `config.toml`:
```toml
# Required settings
srcDir = "/path/to/bear/markdown"
destDir = "/path/to/output"
openai_key = "your-api-key-here"  # Required for GPT-4o
cbm_dir = ".cbm"  # System files location

# Optional settings
logLevel = "INFO"  # Default: INFO
force_generation = false  # Default: false, set to true to force regeneration
image_analysis_prompt = """Custom prompt for GPT-4o"""
```

## Usage

The tool will automatically detect which files need to be regenerated based on modification times of source files and their attachments. You can override this behavior with the force_generation setting in config.toml or using the --force flag.

```bash
# Process only changed files
consolidate-bear-markdown

# Force processing of all files
consolidate-bear-markdown --force
```
