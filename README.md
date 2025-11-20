# Runvoy Documentation Site Generator

This repository automatically generates and deploys the Runvoy project documentation site using GitHub Pages.

## Overview

The documentation site is built automatically from the Runvoy repository using:

- **mkdocs** - Static site generator
- **mkdocs-material** - Professional Material Design theme
- **GitHub Actions** - Automated build and deployment

## How it Works

The generator fetches all markdown files from the [Runvoy repository](https://github.com/runvoy/runvoy), including:

- Root-level documentation files (e.g., `CONTRIBUTING.md`, `SECURITY.md`)
- Files in the `docs/` directory

The build process:

1. **Fetches markdown files** from the Runvoy repo using the GitHub API
2. **Processes the content** with automatic link rewriting (converts `docs/` prefixed links to site-relative paths)
3. **Generates the site** using mkdocs with the Material theme
4. **Deploys to GitHub Pages** automatically on every push to `main`

## Setup & Configuration

### Dependencies

Managed with [uv](https://astral.sh/uv):

```bash
uv pip install mkdocs mkdocs-material requests
```

### Running Locally

Generate the docs site locally:

```bash
uv run generate_docs.py
```

This will:

- Create a `docs/` directory with fetched markdown files
- Generate a `mkdocs.yml` configuration
- Build the static site in `site/`

To preview the site locally:

```bash
uv run mkdocs serve
```

## Deployment

The site deploys automatically via GitHub Actions (`.github/workflows/build-docs.yml`):

- Triggered on pushes to `main` branch or manual workflow dispatch
- Builds the documentation
- Deploys to GitHub Pages

### GitHub Pages Setup

1. Go to repository Settings → Pages
2. Set "Source" to "GitHub Actions"
3. The workflow will automatically run on next push

## Generated Site Structure

All documentation is flattened to the root level:

```
site/
├── index.html              # Homepage (from README.md)
├── AGENTS/
├── ARCHITECTURE/
├── CLI/
├── CODE_OF_CONDUCT/
├── CONTRIBUTING/
├── SECURITY/
├── TESTING_EXAMPLES/
├── TESTING_QUICKSTART/
├── TESTING_STRATEGY/
└── assets/                 # CSS, JS, etc.
```

## Files

- `generate_docs.py` - Main generator script
- `pyproject.toml` - Python project configuration
- `.github/workflows/build-docs.yml` - GitHub Actions workflow
- `mkdocs.yml` - Generated mkdocs configuration (auto-created)
- `docs/` - Generated markdown files (auto-created)
- `site/` - Generated static site (auto-created)
