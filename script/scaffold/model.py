"""Models for scaffolding."""
from __future__ import annotations

import json
from pathlib import Path

import attr

from .const import COMPONENT_DIR, TESTS_DIR


@attr.s
class Info:
    """Info about new integration."""

    domain: str = attr.ib()
    name: str = attr.ib()
    is_new: bool = attr.ib()
    codeowner: str = attr.ib(default=None)
    requirement: str = attr.ib(default=None)
    authentication: str = attr.ib(default=None)
    discoverable: str = attr.ib(default=None)
    oauth2: str = attr.ib(default=None)

    files_added: set[Path] = attr.ib(factory=set)
    tests_added: set[Path] = attr.ib(factory=set)
    examples_added: set[Path] = attr.ib(factory=set)

    @property
    def integration_dir(self) -> Path:
        """Return directory if integration."""
        return COMPONENT_DIR / self.domain

    @property
    def tests_dir(self) -> Path:
        """Return test directory."""
        return TESTS_DIR / self.domain

    @property
    def manifest_path(self) -> Path:
        """Path to the manifest."""
        return COMPONENT_DIR / self.domain / "manifest.json"

    def manifest(self) -> dict:
        """Return integration manifest."""
        return json.loads(self.manifest_path.read_text())

    def update_manifest(self, **kwargs) -> None:
        """Update the integration manifest."""
        print(f"Updating {self.domain} manifest: {kwargs}")
        self.manifest_path.write_text(
            json.dumps({**self.manifest(), **kwargs}, indent=2)
        )

    @property
    def strings_path(self) -> Path:
        """Path to the strings."""
        return COMPONENT_DIR / self.domain / "strings.json"

    def strings(self) -> dict:
        """Return integration strings."""
        if not self.strings_path.exists():
            return {}
        return json.loads(self.strings_path.read_text())

    def update_strings(self, **kwargs) -> None:
        """Update the integration strings."""
        print(f"Updating {self.domain} strings: {list(kwargs)}")
        self.strings_path.write_text(json.dumps({**self.strings(), **kwargs}, indent=2))
