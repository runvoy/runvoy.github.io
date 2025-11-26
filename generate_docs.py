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

import base64
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from string import Template
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
        self.exclude_patterns = {"LICENSE", "CHANGELOG", "AGENTS", ".gitignore", ".github"}
        # Path to the gomarkdoc SGML file
        self.gomarkdoc_file = Path("gomarkdoc")

    def fetch_markdown_files(self) -> dict[str, str]:
        """
        Fetch all markdown files from the Runvoy repo using the Git Trees API.
        Returns a dict of {file_path: content}
        """
        print(f"Fetching markdown files from {self.runvoy_repo}...")

        files = {}
        try:
            # Get the commit SHA for the branch
            ref_url = f"{self.base_url}/git/refs/heads/{self.branch}"
            ref_response = requests.get(ref_url, headers=self.headers)
            ref_response.raise_for_status()
            commit_sha = ref_response.json()["object"]["sha"]

            # Get the recursive tree (all files in one call)
            tree_url = f"{self.base_url}/git/trees/{commit_sha}"
            tree_params = {"recursive": "1"}
            tree_response = requests.get(tree_url, headers=self.headers, params=tree_params)
            tree_response.raise_for_status()
            tree_data = tree_response.json()

            # Filter and fetch markdown files
            for item in tree_data.get("tree", []):
                if item["type"] != "blob":  # Skip directories
                    continue

                file_path = item["path"]

                # Skip excluded files/directories
                path_parts = file_path.split("/")
                if any(
                    part.startswith(pattern)
                    for part in path_parts
                    for pattern in self.exclude_patterns
                ):
                    continue

                # Only process markdown files
                if not file_path.endswith(".md"):
                    continue

                # Fetch the file content using the blob SHA
                blob_url = f"{self.base_url}/git/blobs/{item['sha']}"
                blob_response = requests.get(blob_url, headers=self.headers)
                blob_response.raise_for_status()
                blob_data = blob_response.json()

                # Decode base64 content
                content = base64.b64decode(blob_data["content"]).decode("utf-8")
                files[file_path] = content
                print(f"  ✓ {file_path}")

        except requests.RequestException as e:
            print(f"Error fetching files: {e}")
            if not files:
                print("No files could be fetched. Skipping generation.")
                return {}
        return files

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
            full_path = match.group(2)  # Full path including any prefix
            prefix = match.group(3)  # ./ or . or None
            file_path = match.group(4)  # filename without ./ prefix

            # Skip absolute URLs (http:// or https://)
            if full_path.startswith("http://") or full_path.startswith("https://"):
                return match.group(0)  # Return original match unchanged

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
            r"\[([^\]]+)\]\(((\.[/]?)?([^\)]+\.(?!md)[a-zA-Z]+))\)", replace_non_markdown, content
        )

        # Remove docs/ prefix from markdown links with .md extension
        # (e.g., [text](docs/FILE.md) -> [text](FILE.md))
        content = re.sub(r"\[([^\]]+)\]\(docs/([^\)]+\.md)\)", r"[\1](\2)", content)

        # Remove docs/ prefix and add .md extension if missing
        # (e.g., [text](docs/FILE) -> [text](FILE.md))
        content = re.sub(r"\[([^\]]+)\]\(docs/([^\)]+)\)", r"[\1](\2.md)", content)

        # Handle bare markdown file references without docs/ prefix
        # (e.g., [text](CLI) -> [text](CLI.md))
        # This matches links that look like filenames but don't have file extensions
        # and aren't URLs (no :// in them)
        def add_md_extension(match):
            link_text = match.group(1)
            link_target = match.group(2)
            # Don't add .md if it's already there or if it looks like a URL or anchor
            if (
                not link_target.endswith(".md")
                and "://" not in link_target
                and not link_target.startswith("#")
            ):
                return f"[{link_text}]({link_target}.md)"
            return match.group(0)

        content = re.sub(r"\[([^\]]+)\]\(([A-Z][A-Z_]+)\)", add_md_extension, content)

        # Handle markdown files with relative paths (./FILE.md)
        # Convert to GitHub URLs since they're not in the docs directory
        content = re.sub(
            r"\[([^\]]+)\]\(\.\/([^\)]+\.md)\)",
            lambda m: f"[{m.group(1)}]({github_base}/{m.group(2)})",
            content,
        )

        # Handle non-markdown files with relative paths (./FILE or ./FILE.ext)
        # Convert to GitHub URLs
        content = re.sub(
            r"\[([^\]]+)\]\(\.\/([^\)]+\.(?!md)[^\)]*)\)",
            lambda m: f"[{m.group(1)}]({github_base}/{m.group(2)})",
            content,
        )
        # Also handle files without extension (like ./VERSION)
        content = re.sub(
            r"\[([^\]]+)\]\(\.\/([A-Z_][A-Z_]*)\)",
            lambda m: f"[{m.group(1)}]({github_base}/{m.group(2)})",
            content,
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

    def fetch_version(self) -> str:
        """Fetch the VERSION file from Runvoy repo."""
        url = f"{self.base_url}/contents/VERSION"
        params = {"ref": self.branch}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()

            item = response.json()
            content_response = requests.get(item["download_url"], headers=self.headers)
            content_response.raise_for_status()

            return content_response.text.strip()
        except requests.RequestException as e:
            print(f"Warning: Could not fetch VERSION file: {e}")
            return ""

    def create_mkdocs_config(self, files: dict[str, str]):
        """Generate mkdocs.yml configuration using template."""
        print("\nGenerating mkdocs.yml configuration...")

        # Build navigation from file structure
        nav = self._build_nav(files)

        # Fetch version to enrich site name
        version = self.fetch_version()
        site_name = "Runvoy"
        if version:
            site_name = f"Runvoy {version}"

        # Generate build timestamp
        build_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Generate nav section as YAML string
        nav_buffer = StringIO()
        nav_buffer.write("nav:\n")
        for item in nav:
            self._write_nav_item(nav_buffer, item, indent=2)
        nav_section = nav_buffer.getvalue()

        # Read template file
        template_path = Path(__file__).parent / "templates" / "mkdocs.yml.template"
        with open(template_path) as f:
            template_content = f.read()

        # Substitute placeholders
        template = Template(template_content)
        config_content = template.substitute(
            site_name=site_name, build_time=build_time, nav_section=nav_section
        )

        # Write the final configuration
        with open(self.mkdocs_config, "w") as f:
            f.write(config_content)

        print("  ✓ mkdocs.yml created")

    def _build_nav(self, files: dict[str, str]) -> list:
        """Build navigation structure from files (flattened)."""
        nav = []

        # Add index if it exists
        if "README.md" in files:
            nav.append({"Home": "README.md"})

        # Separate regular docs from API reference
        regular_files = []
        api_reference_file = None

        for file_path in sorted(files.keys()):
            if file_path == "README.md":
                continue

            # Flatten docs/ prefix
            display_path = file_path
            if file_path.startswith("docs/"):
                display_path = file_path[5:]  # Remove "docs/" prefix

            # Handle API reference specially
            if display_path == "API_REFERENCE.md":
                api_reference_file = display_path
            else:
                regular_files.append((display_path, display_path))

        # Add regular documentation files
        for file_path, file_ref in sorted(regular_files):
            readable_title = self._filename_to_title(file_path)
            nav.append({readable_title: file_ref})

        # Add API Reference in root nav if it exists
        if api_reference_file:
            nav.append({"API Reference": api_reference_file})

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

    def process_gomarkdoc(self) -> dict[str, str]:
        """
        Process Go documentation from gomarkdoc SGML file.
        Converts SGML to markdown and returns a dict of {file_path: content}.
        """
        if not self.gomarkdoc_file.exists():
            print(f"Warning: {self.gomarkdoc_file} not found. Skipping Go documentation.")
            return {}

        print(f"\nProcessing Go documentation from {self.gomarkdoc_file}...")
        files = {}

        try:
            # Read the SGML content
            with open(self.gomarkdoc_file, encoding="utf-8") as f:
                sgml_content = f.read()

            # Convert SGML to markdown
            # Basic SGML to markdown conversion for gomarkdoc output
            markdown_content = self._sgml_to_markdown(sgml_content)

            # Save as API reference documentation in root
            files["API_REFERENCE.md"] = markdown_content
            print("  ✓ API_REFERENCE.md")

        except (OSError, UnicodeDecodeError) as e:
            print(f"Error processing {self.gomarkdoc_file}: {e}")
            return {}

        return files

    def _sgml_to_markdown(self, sgml_content: str) -> str:
        """
        Convert SGML content to markdown.
        Handles common SGML tags used by gomarkdoc.
        """
        content = sgml_content

        # Convert common SGML tags to markdown
        # Package declarations
        content = re.sub(r"<package[^>]*>([^<]+)</package>", r"## Package: \1", content)

        # Function/method declarations
        content = re.sub(r"<func[^>]*>([^<]+)</func>", r"### \1", content)
        content = re.sub(r"<method[^>]*>([^<]+)</method>", r"### \1", content)

        # Type declarations
        content = re.sub(r"<type[^>]*>([^<]+)</type>", r"### Type: \1", content)

        # Code blocks
        content = re.sub(r"<code[^>]*>(.*?)</code>", r"```go\n\1\n```", content, flags=re.DOTALL)

        # Links
        content = re.sub(r"<a[^>]*href=['\"]([^'\"]+)['\"][^>]*>([^<]+)</a>", r"[\2](\1)", content)

        # Paragraphs
        content = re.sub(r"<p[^>]*>", "", content)
        content = re.sub(r"</p>", "\n\n", content)

        # Lists
        content = re.sub(r"<ul[^>]*>", "", content)
        content = re.sub(r"</ul>", "\n", content)
        content = re.sub(r"<ol[^>]*>", "", content)
        content = re.sub(r"</ol>", "\n", content)
        content = re.sub(r"<li[^>]*>", "- ", content)
        content = re.sub(r"</li>", "\n", content)

        # Emphasis
        content = re.sub(r"<em[^>]*>([^<]+)</em>", r"*\1*", content)
        content = re.sub(r"<strong[^>]*>([^<]+)</strong>", r"**\1**", content)

        # Headings
        content = re.sub(r"<h1[^>]*>([^<]+)</h1>", r"# \1", content)
        content = re.sub(r"<h2[^>]*>([^<]+)</h2>", r"## \1", content)
        content = re.sub(r"<h3[^>]*>([^<]+)</h3>", r"### \1", content)
        content = re.sub(r"<h4[^>]*>([^<]+)</h4>", r"#### \1", content)

        # Remove remaining SGML tags
        content = re.sub(r"<[^>]+>", "", content)

        # Clean up extra whitespace
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content.strip()

    def generate_site(self):
        """Build the site using mkdocs."""
        print("\nGenerating site with mkdocs...")

        try:
            subprocess.run(
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

        # Process Go documentation from gomarkdoc SGML file
        gomarkdoc_files = self.process_gomarkdoc()

        # Merge Go documentation files into main files dict
        files.update(gomarkdoc_files)

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
