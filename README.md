# Runvoy Documentation Site Generator

This repository automatically generates and deploys the Runvoy project documentation site using GitHub Pages.

## Overview

The documentation site is built automatically from the Runvoy repository using:

- **mkdocs** - Static site generator
- **mkdocs-material** - Professional Material Design theme
- **GitHub Actions** - Automated build and deployment

## How it Works

The generator fetches all markdown files from the [Runvoy repository](https://github.com/runvoy/runvoy), including:

- Root-level documentation files (e.g., `CONTRIBUTING.md`, `SECURITY.md`, `AGENTS.md`)
- Files in the `docs/` directory (e.g., `ARCHITECTURE.md`, `CLI.md`, `TESTING_*.md`)

The build process:

1. **Fetches markdown files** from the Runvoy repo using the GitHub API
2. **Flattens the hierarchy** - files from `docs/` subdirectory are placed at root level
3. **Rewrites links** intelligently:
   - Removes `docs/` prefix from internal markdown links
   - Converts non-markdown file links (`.yml`, `.json`, etc.) to GitHub repository URLs
   - Handles relative paths by linking to the GitHub repository
4. **Generates readable navigation titles** (e.g., `CODE_OF_CONDUCT.md` → "Code of Conduct", `CLI.md` → "CLI")
5. **Builds the site** using mkdocs with the Material theme
6. **Deploys to GitHub Pages** automatically on every push to `main`

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

## Link Rewriting

The generator automatically handles various types of links in the markdown files:

| Link Type | Original | Rewritten |
|-----------|----------|-----------|
| Docs with prefix | `[text](docs/ARCHITECTURE.md)` | `[text](ARCHITECTURE.md)` |
| Bare doc names | `[text](CLI)` | `[text](CLI.md)` |
| Config files | `[text](.runvoy/example.yml)` | `[text](https://github.com/runvoy/runvoy/blob/main/.runvoy/example.yml)` |
| External files | `[text](./CHANGELOG.md)` | `[text](https://github.com/runvoy/runvoy/blob/main/CHANGELOG.md)` |
| Version file | `[text](./VERSION)` | `[text](https://github.com/runvoy/runvoy/blob/main/VERSION)` |
| Non-markdown | `[text](config.json)` | `[text](https://github.com/runvoy/runvoy/blob/main/config.json)` |

This ensures all links work correctly on the generated documentation site while external files link back to the repository.

## Generated Site Structure

All documentation is flattened to the root level:

```
site/
├── index.html              # Homepage (from README.md)
├── Agents/                 # From AGENTS.md
├── Architecture/           # From docs/ARCHITECTURE.md
├── CLI/                    # From docs/CLI.md
├── Code of Conduct/        # From CODE_OF_CONDUCT.md
├── Contributing/           # From CONTRIBUTING.md
├── Security/               # From SECURITY.md
├── Testing Examples/       # From docs/TESTING_EXAMPLES.md
├── Testing Quickstart/     # From docs/TESTING_QUICKSTART.md
├── Testing Strategy/       # From docs/TESTING_STRATEGY.md
└── assets/                 # CSS, JS, etc.
```

## Files

- `generate_docs.py` - Main generator script
- `pyproject.toml` - Python project configuration
- `.github/workflows/build-docs.yml` - GitHub Actions workflow
- `mkdocs.yml` - Generated mkdocs configuration (auto-created)
- `docs/` - Generated markdown files (auto-created)
- `site/` - Generated static site (auto-created)
