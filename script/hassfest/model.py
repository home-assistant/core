"""Models for manifest validator."""
from __future__ import annotations

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

    specific_integrations: list[pathlib.Path] | None = attr.ib()
    root: pathlib.Path = attr.ib()
    action: str = attr.ib()
    requirements: bool = attr.ib()
    errors: list[Error] = attr.ib(factory=list)
    cache: dict[str, Any] = attr.ib(factory=dict)
    plugins: set[str] = attr.ib(factory=set)

    def add_error(self, *args: Any, **kwargs: Any) -> None:
        """Add an error."""
        self.errors.append(Error(*args, **kwargs))


@attr.s
class Brand:
    """Represent a brand in our validator."""

    @classmethod
    def load_dir(cls, path: pathlib.Path, config: Config) -> dict[str, Brand]:
        """Load all brands in a directory."""
        assert path.is_dir()
        brands: dict[str, Brand] = {}
        for fil in path.iterdir():
            brand = cls(fil)
            brand.load_brand(config)
            brands[brand.domain] = brand

        return brands

    path: pathlib.Path = attr.ib()
    _brand: dict[str, Any] | None = attr.ib(default=None)

    @property
    def brand(self) -> dict[str, Any]:
        """Guarded access to brand."""
        assert self._brand is not None, "brand has not been loaded"
        return self._brand

    @property
    def domain(self) -> str:
        """Integration domain."""
        return self.path.stem

    @property
    def name(self) -> str | None:
        """Return name of the integration."""
        return self.brand.get("name")

    @property
    def integrations(self) -> list[str]:
        """Return the sub integrations of this brand."""
        return self.brand.get("integrations", [])

    @property
    def iot_standards(self) -> list[str]:
        """Return list of supported IoT standards."""
        return self.brand.get("iot_standards", [])

    def load_brand(self, config: Config) -> None:
        """Load brand file."""
        if not self.path.is_file():
            config.add_error("model", f"Brand file {self.path} not found")
            return

        try:
            brand: dict[str, Any] = json.loads(self.path.read_text())
        except ValueError as err:
            config.add_error(
                "model", f"Brand file {self.path.name} contains invalid JSON: {err}"
            )
            return

        self._brand = brand


@attr.s
class Integration:
    """Represent an integration in our validator."""

    @classmethod
    def load_dir(cls, path: pathlib.Path) -> dict[str, Integration]:
        """Load all integrations in a directory."""
        assert path.is_dir()
        integrations: dict[str, Integration] = {}
        for fil in path.iterdir():
            if fil.is_file() or fil.name == "__pycache__":
                continue

            init = fil / "__init__.py"
            manifest = fil / "manifest.json"
            if not init.exists() and not manifest.exists():
                print(
                    f"Warning: {init} and manifest.json missing, "
                    "skipping directory. If this is your development "
                    "environment, you can safely delete this folder."
                )
                continue

            integration = cls(fil)
            integration.load_manifest()
            integrations[integration.domain] = integration

        return integrations

    path: pathlib.Path = attr.ib()
    _manifest: dict[str, Any] | None = attr.ib(default=None)
    errors: list[Error] = attr.ib(factory=list)
    warnings: list[Error] = attr.ib(factory=list)
    translated_name: bool = attr.ib(default=False)

    @property
    def manifest(self) -> dict[str, Any]:
        """Guarded access to manifest."""
        assert self._manifest is not None, "manifest has not been loaded"
        return self._manifest

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
        name: str = self.manifest["name"]
        return name

    @property
    def quality_scale(self) -> str | None:
        """Return quality scale of the integration."""
        return self.manifest.get("quality_scale")

    @property
    def config_flow(self) -> bool:
        """Return if the integration has a config flow."""
        return self.manifest.get("config_flow", False)

    @property
    def requirements(self) -> list[str]:
        """List of requirements."""
        return self.manifest.get("requirements", [])

    @property
    def dependencies(self) -> list[str]:
        """List of dependencies."""
        return self.manifest.get("dependencies", [])

    @property
    def supported_by(self) -> str:
        """Return the integration supported by this virtual integration."""
        return self.manifest.get("supported_by", {})

    @property
    def integration_type(self) -> str:
        """Get integration_type."""
        return self.manifest.get("integration_type", "hub")

    @property
    def iot_class(self) -> str | None:
        """Return the integration IoT Class."""
        return self.manifest.get("iot_class")

    @property
    def iot_standards(self) -> list[str]:
        """Return the IoT standard supported by this virtual integration."""
        return self.manifest.get("iot_standards", [])

    def add_error(self, *args: Any, **kwargs: Any) -> None:
        """Add an error."""
        self.errors.append(Error(*args, **kwargs))

    def add_warning(self, *args: Any, **kwargs: Any) -> None:
        """Add a warning."""
        self.warnings.append(Error(*args, **kwargs))

    def load_manifest(self) -> None:
        """Load manifest."""
        manifest_path = self.path / "manifest.json"
        if not manifest_path.is_file():
            self.add_error("model", f"Manifest file {manifest_path} not found")
            return

        try:
            manifest: dict[str, Any] = json.loads(manifest_path.read_text())
        except ValueError as err:
            self.add_error("model", f"Manifest contains invalid JSON: {err}")
            return

        self._manifest = manifest
