"""Models for manifest validator."""
from __future__ import annotations

import importlib
import json
import pathlib
from typing import Any

import attr


@attr.s
class Error:
    """Error validating an integration."""

    plugin: str = attr.ib()
    error: str = attr.ib()
    fixable: bool = attr.ib(default=False)

    def __str__(self) -> str:
        """Represent error as string."""
        return f"[{self.plugin.upper()}] {self.error}"


@attr.s
class Config:
    """Config for the run."""

    specific_integrations: pathlib.Path | None = attr.ib()
    root: pathlib.Path = attr.ib()
    action: str = attr.ib()
    requirements: bool = attr.ib()
    errors: list[Error] = attr.ib(factory=list)
    cache: dict[str, Any] = attr.ib(factory=dict)

    def add_error(self, *args: Any, **kwargs: Any) -> None:
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

    path: pathlib.Path = attr.ib()
    manifest: dict[str, Any] | None = attr.ib(default=None)
    errors: list[Error] = attr.ib(factory=list)
    warnings: list[Error] = attr.ib(factory=list)

    @property
    def domain(self) -> str:
        """Integration domain."""
        return self.path.name

    @property
    def core(self) -> bool:
        """Core integration."""
        return self.path.as_posix().startswith("homeassistant/components")

    @property
    def disabled(self) -> str | None:
        """Return if integration is disabled."""
        return self.manifest.get("disabled")

    @property
    def name(self) -> str:
        """Return name of the integration."""
        return self.manifest["name"]

    @property
    def quality_scale(self) -> str:
        """Return quality scale of the integration."""
        return self.manifest.get("quality_scale")

    @property
    def config_flow(self) -> str:
        """Return if the integration has a config flow."""
        return self.manifest.get("config_flow")

    @property
    def requirements(self) -> list[str]:
        """List of requirements."""
        return self.manifest.get("requirements", [])

    @property
    def dependencies(self) -> list[str]:
        """List of dependencies."""
        return self.manifest.get("dependencies", [])

    def add_error(self, *args: Any, **kwargs: Any) -> None:
        """Add an error."""
        self.errors.append(Error(*args, **kwargs))

    def add_warning(self, *args: Any, **kwargs: Any) -> None:
        """Add an warning."""
        self.warnings.append(Error(*args, **kwargs))

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
