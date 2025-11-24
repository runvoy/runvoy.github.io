# Serve the documentation site locally
server:
	uv run mkdocs serve

# Build the documentation site locally
build:
	uv run mkdocs build

# Generate the documentation site
generate:
	uv run generate_docs.py

# Setup the project
setup:
	uv sync

clean:
	rm -rf docs site
	git clean -f .

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check --fix .
	uv run ruff format --check .

[working-directory: '.github/actions/cleanup-deployments']
build-cleanup-action:
	npm run build
