#!/usr/bin/env python3
"""
Runvoy Docs Generator

Fetches markdown files from the Runvoy repo and generates a docs site using mkdocs.

Features:
- Fetches all markdown files from the repository (root + subdirectories)
- Flattens hierarchy: docs/FILE.md becomes FILE.md in the generated site
- Rewrites links:
  * Removes docs/ prefix from internal links
  * Strips links to non-documentation files (.yml, .yaml, etc.)
  * Converts broken relative links to anchors
- Generates mkdocs config with Material theme
- Supports GitHub Pages deployment via GitHub Actions
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import requests


class RunvoyDocsGenerator:
    def __init__(
        self,
        github_token: Optional[str] = None,
        runvoy_repo: str = "runvoy/runvoy",
        branch: str = "main",
    ):
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN")
        self.runvoy_repo = runvoy_repo
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{runvoy_repo}"
        self.headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            self.headers["Authorization"] = f"token {self.github_token}"

        self.local_docs_dir = Path("docs")
        self.site_dir = Path("site")
        self.mkdocs_config = Path("mkdocs.yml")
        # Files to exclude from the docs
        self.exclude_patterns = {"LICENSE", "CHANGELOG", ".gitignore", ".github"}

    def fetch_markdown_files(self) -> dict[str, str]:
        """
        Fetch all markdown files from the Runvoy repo.
        Returns a dict of {file_path: content}
        """
        print(f"Fetching markdown files from {self.runvoy_repo}...")

        files = {}
        try:
            self._fetch_tree("", "", files)
        except requests.RequestException as e:
            print(f"Error fetching files: {e}")
            if not files:
                print("No files could be fetched. Skipping generation.")
                return {}
        return files

    def _fetch_tree(self, path: str, relative_path: str, files: dict[str, str]):
        """Recursively fetch files from a directory tree."""
        url = f"{self.base_url}/contents/{path}" if path else f"{self.base_url}/contents"
        params = {"ref": self.branch}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            items = response.json()
            if not isinstance(items, list):
                items = [items]

            for item in items:
                # Skip excluded directories
                if any(item["name"].startswith(pattern) for pattern in self.exclude_patterns):
                    continue

                if item["type"] == "file" and item["name"].endswith(".md"):
                    # Fetch the file content
                    content_response = requests.get(
                        item["download_url"], headers=self.headers
                    )
                    content_response.raise_for_status()

                    file_relative_path = f"{relative_path}/{item['name']}" if relative_path else item["name"]
                    files[file_relative_path] = content_response.text
                    print(f"  ✓ {file_relative_path}")

                elif item["type"] == "dir":
                    new_relative = f"{relative_path}/{item['name']}" if relative_path else item["name"]
                    self._fetch_tree(item["path"], new_relative, files)

        except requests.RequestException as e:
            print(f"Error fetching {path}: {e}")

    def rewrite_links(self, content: str, file_path: str) -> str:
        """
        Rewrite markdown links to match the generated site structure.
        - Removes docs/ prefix from internal markdown links, keeping .md extension
        - Converts non-markdown file links to GitHub repository URLs
        - Handles bare documentation file references (e.g., CLI -> CLI.md)
        - Handles relative paths by converting to GitHub URLs
        """
        github_base = f"https://github.com/{self.runvoy_repo}/blob/{self.branch}"

        # Convert non-markdown file links to GitHub repository URLs
        # Pattern: [text](path/to/file.ext) where ext is not md
        # This handles .runvoy/*, *.yml, *.yaml, *.json, LICENSE, CHANGELOG, etc.
        def replace_non_markdown(match):
            link_text = match.group(1)
            full_path = match.group(2)
            prefix = match.group(3)  # ./ or . or None
            file_path = match.group(4)  # filename without ./ prefix

            # If there's a . prefix (e.g., .runvoy/), reconstruct with it
            if prefix == ".":
                file_path = f".{file_path}"
            # If ./ prefix, just use the file_path (relative prefix already removed)

            return f"[{link_text}]({github_base}/{file_path})"

        # Match [text](optional_prefix/file.extension) where extension is not md
        # Group 2: full path with optional prefix
        # Group 3: optional prefix (./ or .)
        # Group 4: filename after any ./  prefix
        content = re.sub(
            r'\[([^\]]+)\]\(((\.[/]?)?([^\)]+\.(?!md)[a-zA-Z]+))\)',
            replace_non_markdown,
            content
        )

        # Remove docs/ prefix from markdown links with .md extension
        # (e.g., [text](docs/FILE.md) -> [text](FILE.md))
        content = re.sub(r'\[([^\]]+)\]\(docs/([^\)]+\.md)\)', r'[\1](\2)', content)

        # Remove docs/ prefix and add .md extension if missing
        # (e.g., [text](docs/FILE) -> [text](FILE.md))
        content = re.sub(r'\[([^\]]+)\]\(docs/([^\)]+)\)', r'[\1](\2.md)', content)

        # Handle bare markdown file references without docs/ prefix
        # (e.g., [text](CLI) -> [text](CLI.md))
        # This matches links that look like filenames but don't have file extensions
        # and aren't URLs (no :// in them)
        def add_md_extension(match):
            link_text = match.group(1)
            link_target = match.group(2)
            # Don't add .md if it's already there or if it looks like a URL or anchor
            if not link_target.endswith('.md') and '://' not in link_target and not link_target.startswith('#'):
                return f"[{link_text}]({link_target}.md)"
            return match.group(0)

        content = re.sub(r'\[([^\]]+)\]\(([A-Z][A-Z_]+)\)', add_md_extension, content)

        # Handle markdown files with relative paths (./FILE.md)
        # Convert to GitHub URLs since they're not in the docs directory
        content = re.sub(
            r'\[([^\]]+)\]\(\.\/([^\)]+\.md)\)',
            lambda m: f"[{m.group(1)}]({github_base}/{m.group(2)})",
            content
        )

        # Handle non-markdown files with relative paths (./FILE or ./FILE.ext)
        # Convert to GitHub URLs
        content = re.sub(
            r'\[([^\]]+)\]\(\.\/([^\)]+\.(?!md)[^\)]*)\)',
            lambda m: f"[{m.group(1)}]({github_base}/{m.group(2)})",
            content
        )
        # Also handle files without extension (like ./VERSION)
        content = re.sub(
            r'\[([^\]]+)\]\(\.\/([A-Z_][A-Z_]*)\)',
            lambda m: f"[{m.group(1)}]({github_base}/{m.group(2)})",
            content
        )

        return content

    def write_markdown_files(self, files: dict[str, str]):
        """Write fetched markdown files to local docs directory, flattening the hierarchy."""
        print("\nWriting markdown files to local docs directory...")

        # Clear and create docs directory
        if self.local_docs_dir.exists():
            shutil.rmtree(self.local_docs_dir)
        self.local_docs_dir.mkdir(parents=True)

        for file_path, content in files.items():
            # Flatten hierarchy: docs/SOMETHING.md -> SOMETHING.md
            flattened_path = file_path
            if file_path.startswith("docs/"):
                flattened_path = file_path[5:]  # Remove "docs/" prefix

            # Rewrite links in content
            content = self.rewrite_links(content, file_path)

            # Create nested directories if needed
            full_path = self.local_docs_dir / flattened_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w") as f:
                f.write(content)
            print(f"  ✓ {flattened_path}")

    def create_mkdocs_config(self, files: dict[str, str]):
        """Generate mkdocs.yml configuration."""
        print("\nGenerating mkdocs.yml configuration...")

        # Build navigation from file structure
        nav = self._build_nav(files)

        config = {
            "site_name": "Runvoy Documentation",
            "docs_dir": "docs",
            "site_dir": "site",
            "theme": {"name": "material"},
            "nav": nav,
        }

        with open(self.mkdocs_config, "w") as f:
            # Manual YAML writing to maintain readability
            f.write("site_name: Runvoy Documentation\n")
            f.write("docs_dir: docs\n")
            f.write("site_dir: site\n")
            f.write("theme:\n")
            f.write("  name: material\n")
            f.write("nav:\n")
            for item in nav:
                self._write_nav_item(f, item, indent=2)

        print(f"  ✓ mkdocs.yml created")

    def _build_nav(self, files: dict[str, str]) -> list:
        """Build navigation structure from files (flattened)."""
        nav = []

        # Add index if it exists
        if "README.md" in files:
            nav.append({"Home": "README.md"})

        # Flatten all files and add to nav in sorted order
        flattened_files = []
        for file_path in sorted(files.keys()):
            if file_path == "README.md":
                continue

            # Flatten docs/ prefix
            display_path = file_path
            if file_path.startswith("docs/"):
                display_path = file_path[5:]  # Remove "docs/" prefix

            flattened_files.append((display_path, display_path))

        # Add all files to nav with readable titles
        for file_path, file_ref in sorted(flattened_files):
            readable_title = self._filename_to_title(file_path)
            nav.append({readable_title: file_ref})

        return nav

    def _filename_to_title(self, filename: str) -> str:
        """Convert filename to readable title.

        Examples:
            CODE_OF_CONDUCT.md -> Code of Conduct
            TESTING_QUICKSTART.md -> Testing Quickstart
            CLI.md -> CLI
            ARCHITECTURE.md -> Architecture
        """
        # Remove .md extension if present
        name = filename.replace(".md", "")

        # Common words that should be lowercase (except at start)
        lowercase_words = {"of", "and", "or", "the", "a", "an", "in", "on", "at", "by"}

        # Split by underscore and process each word
        words = name.split("_")
        title_words = []
        for i, word in enumerate(words):
            word_lower = word.lower()
            # Keep all-caps acronyms as-is (e.g., CLI, AWS) unless they're common words
            if len(word) <= 3 and word.isupper() and word_lower not in lowercase_words:
                title_words.append(word)
            # Common words should be lowercase (except first word)
            elif word_lower in lowercase_words and i > 0:
                title_words.append(word_lower)
            else:
                # Capitalize first letter, lowercase the rest
                title_words.append(word.capitalize())

        title = " ".join(title_words)
        return title

    def _write_nav_item(self, f, item: dict, indent: int = 0):
        """Recursively write navigation items to YAML."""
        prefix = " " * indent
        for key, value in item.items():
            if isinstance(value, str):
                f.write(f"{prefix}- {key}: {value}\n")
            elif isinstance(value, list):
                f.write(f"{prefix}- {key}:\n")
                for sub_item in value:
                    self._write_nav_item(f, sub_item, indent + 2)
            elif isinstance(value, dict):
                f.write(f"{prefix}- {key}:\n")
                self._write_nav_item(f, value, indent + 2)

    def fetch_readme(self) -> str:
        """Fetch the README.md from Runvoy repo as the index."""
        print("Fetching README.md from Runvoy repo...")

        url = f"{self.base_url}/contents/README.md"
        params = {"ref": self.branch}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            item = response.json()
            content_response = requests.get(item["download_url"], headers=self.headers)
            content_response.raise_for_status()

            return content_response.text
        except requests.RequestException as e:
            print(f"Error fetching README.md: {e}")
            return ""

    def add_readme_to_docs(self):
        """Add Runvoy README.md as index to docs."""
        readme_content = self.fetch_readme()
        if readme_content:
            # Apply link rewriting to README
            readme_content = self.rewrite_links(readme_content, "README.md")
            readme_path = self.local_docs_dir / "README.md"
            with open(readme_path, "w") as f:
                f.write(readme_content)
            print("  ✓ README.md added to docs")

    def generate_site(self):
        """Build the site using mkdocs."""
        print("\nGenerating site with mkdocs...")

        try:
            result = subprocess.run(
                ["mkdocs", "build"],
                check=True,
                capture_output=True,
                text=True,
            )
            print("  ✓ Site generated successfully")
            print(f"  Site location: {self.site_dir.absolute()}")
        except subprocess.CalledProcessError as e:
            print(f"Error generating site: {e}")
            print(f"stdout: {e.stdout}")
            print(f"stderr: {e.stderr}")
            raise

    def run(self):
        """Run the full docs generation pipeline."""
        print("=" * 60)
        print("Runvoy Docs Generator")
        print("=" * 60)

        # Fetch files from Runvoy repo
        files = self.fetch_markdown_files()

        if not files:
            print("\nNo markdown files could be fetched from the repository.")
            print("Skipping site generation.")
            return

        # Write files locally
        self.write_markdown_files(files)

        # Add README as index
        self.add_readme_to_docs()

        # Create mkdocs config
        self.create_mkdocs_config(files)

        # Generate site
        self.generate_site()

        print("\n" + "=" * 60)
        print("✓ Docs generation complete!")
        print("=" * 60)


if __name__ == "__main__":
    generator = RunvoyDocsGenerator()
    generator.run()
