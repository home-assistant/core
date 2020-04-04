"""Models for manifest validator."""
import importlib
import json
import pathlib
from typing import Any, Dict, List

import attr


@attr.s
class Error:
    """Error validating an integration."""

    plugin = attr.ib(type=str)
    error = attr.ib(type=str)
    fixable = attr.ib(type=bool, default=False)

    def __str__(self) -> str:
        """Represent error as string."""
        return "[{}] {}".format(self.plugin.upper(), self.error)


@attr.s
class Config:
    """Config for the run."""

    root = attr.ib(type=pathlib.Path)
    action = attr.ib(type=str)
    errors = attr.ib(type=List[Error], factory=list)
    cache = attr.ib(type=Dict[str, Any], factory=dict)

    def add_error(self, *args, **kwargs):
        """Add an error."""
        self.errors.append(Error(*args, **kwargs))


@attr.s
class Integration:
    """Represent an integration in our validator."""

    @classmethod
    def load_dir(cls, path: pathlib.Path):
        """Load all integrations in a directory."""
        assert path.is_dir()
        integrations = {}
        for fil in path.iterdir():
            if fil.is_file() or fil.name == "__pycache__":
                continue

            init = fil / "__init__.py"
            if not init.exists():
                print(
                    f"Warning: {init} missing, skipping directory. "
                    "If this is your development environment, "
                    "you can safely delete this folder."
                )
                continue

            integration = cls(fil)
            integration.load_manifest()
            integrations[integration.domain] = integration

        return integrations

    path = attr.ib(type=pathlib.Path)
    manifest = attr.ib(type=dict, default=None)
    errors = attr.ib(type=List[Error], factory=list)

    @property
    def domain(self) -> str:
        """Integration domain."""
        return self.path.name

    @property
    def requirements(self) -> List[str]:
        """List of requirements."""
        return self.manifest.get("requirements", [])

    @property
    def dependencies(self) -> List[str]:
        """List of dependencies."""
        return self.manifest.get("dependencies", [])

    def add_error(self, *args, **kwargs):
        """Add an error."""
        self.errors.append(Error(*args, **kwargs))

    def load_manifest(self) -> None:
        """Load manifest."""
        manifest_path = self.path / "manifest.json"
        if not manifest_path.is_file():
            self.add_error("model", f"Manifest file {manifest_path} not found")
            return

        try:
            manifest = json.loads(manifest_path.read_text())
        except ValueError as err:
            self.add_error("model", f"Manifest contains invalid JSON: {err}")
            return

        self.manifest = manifest

    def import_pkg(self, platform=None):
        """Import the Python file."""
        pkg = f"homeassistant.components.{self.domain}"
        if platform is not None:
            pkg += f".{platform}"
        return importlib.import_module(pkg)
