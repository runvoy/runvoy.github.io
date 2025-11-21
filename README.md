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

1. **Fetches markdown files** from the Runvoy repo using the GitHub Git Trees API (efficient single-call recursive tree fetch)
2. **Fetches VERSION file** and includes it in the site name (e.g., "Runvoy Documentation 1.2.3")
3. **Flattens the hierarchy** - files from `docs/` subdirectory are placed at root level
4. **Rewrites links** intelligently:
   - Removes `docs/` prefix from internal markdown links
   - Converts non-markdown file links (`.yml`, `.json`, etc.) to GitHub repository URLs
   - Handles relative paths by linking to the GitHub repository
5. **Generates readable navigation titles** (e.g., `CODE_OF_CONDUCT.md` → "Code of Conduct", `CLI.md` → "CLI")
6. **Builds the site** using mkdocs with the Material theme
7. **Deploys to GitHub Pages** automatically on every push to `main` or daily via scheduled workflow

## Setup & Configuration

### Dependencies

Managed with [uv](https://astral.sh/uv):

```bash
# Install runtime dependencies only
uv sync

# Install all dependencies including dev tools (ruff)
uv sync --extra dev
# or
uv sync --all-extras
```

This installs:

- **Runtime dependencies**: `mkdocs`, `mkdocs-material`, `requests`
- **Development dependencies** (with `--extra dev`): `ruff` (code linting and formatting)

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

## Code Quality

This project uses [ruff](https://docs.astral.sh/ruff/) for code linting and formatting:

- **Linting**: Checks code for errors and style issues (pycodestyle, pyflakes, isort, flake8-bugbear, etc.)
- **Formatting**: Ensures consistent code style across the codebase
- **Configuration**: Defined in `pyproject.toml` under `[tool.ruff]`

**Note**: Make sure dev dependencies are installed first:
```bash
uv sync --extra dev
```

To run linting and formatting checks locally:

```bash
uv run ruff check .
uv run ruff format --check .
```

To auto-fix issues:

```bash
uv run ruff check --fix .
uv run ruff format .
```

## Deployment

The site deploys automatically via GitHub Actions (`.github/workflows/build-docs.yml`):

- **Triggered on pushes** to `main` branch
- **Runs daily** via scheduled cronjob (midnight UTC)
- **Manual trigger** via workflow dispatch
- **Runs code quality checks** (ruff linting and formatting) before building
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

```text
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
