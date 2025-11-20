#!/usr/bin/env python3
"""
Runvoy Docs Generator

Fetches markdown files from the 🚀 Runvoy repo and generates a docs site using mkdocs.
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
        self._fetch_tree("", "", files)
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
        Replaces relative docs/ links with the correct site paths.
        """
        # Remove docs/ prefix from links
        content = re.sub(r'\[([^\]]+)\]\(docs/([^\)]+)\.md\)', r'[\1](\2)', content)
        # Also handle links without .md extension
        content = re.sub(r'\[([^\]]+)\]\(docs/([^\)]+)\)', r'[\1](\2)', content)

        return content

    def write_markdown_files(self, files: dict[str, str]):
        """Write fetched markdown files to local docs directory."""
        print("\nWriting markdown files to local docs directory...")

        # Clear and create docs directory
        if self.local_docs_dir.exists():
            shutil.rmtree(self.local_docs_dir)
        self.local_docs_dir.mkdir(parents=True)

        for file_path, content in files.items():
            # Rewrite links in content
            content = self.rewrite_links(content, file_path)

            # Create nested directories if needed
            full_path = self.local_docs_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w") as f:
                f.write(content)
            print(f"  ✓ {file_path}")

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
        """Build navigation structure from files."""
        nav = []

        # Add index if it exists
        if "README.md" in files:
            nav.append({"Home": "README.md"})

        # Group files by directory
        dirs = {}
        for file_path in sorted(files.keys()):
            if file_path == "README.md":
                continue

            parts = file_path.split("/")
            if len(parts) > 1:
                dir_name = parts[0]
                if dir_name not in dirs:
                    dirs[dir_name] = []
                dirs[dir_name].append(file_path)
            else:
                # Root level files
                nav.append({file_path.replace(".md", ""): file_path})

        # Add directories to nav
        for dir_name in sorted(dirs.keys()):
            section = {dir_name: []}
            for file_path in dirs[dir_name]:
                file_name = file_path.split("/")[-1]
                section[dir_name].append({file_name.replace(".md", ""): file_path})
            nav.append(section)

        return nav

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
