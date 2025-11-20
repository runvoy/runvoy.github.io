# Serve the documentation site locally
dev-server:
	uv run mkdocs serve

# Build the documentation site locally
dev-build:
	uv run mkdocs build

# Generate the documentation site
dev-generate:
	uv run generate_docs.py

# Setup the project
setup:
	uv sync
