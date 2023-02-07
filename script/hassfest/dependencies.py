"""Validate dependencies."""
from __future__ import annotations

import ast
from pathlib import Path

from homeassistant.const import Platform
from homeassistant.requirements import DISCOVERY_INTEGRATIONS

from .model import Config, Integration


class ImportCollector(ast.NodeVisitor):
    """Collect all integrations referenced."""

    def __init__(self, integration: Integration) -> None:
        """Initialize the import collector."""
        self.integration = integration
        self.referenced: dict[Path, set[str]] = {}

        # Current file or dir we're inspecting
        self._cur_fil_dir: Path | None = None

    def collect(self) -> None:
        """Collect imports from a source file."""
        for fil in self.integration.path.glob("**/*.py"):
            if not fil.is_file():
                continue

            self._cur_fil_dir = fil.relative_to(self.integration.path)
            self.referenced[self._cur_fil_dir] = set()
            self.visit(ast.parse(fil.read_text()))
            self._cur_fil_dir = None

    def _add_reference(self, reference_domain: str) -> None:
        """Add a reference."""
        assert self._cur_fil_dir
        self.referenced[self._cur_fil_dir].add(reference_domain)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit ImportFrom node."""
        if node.module is None:
            return

        # Exception: we will allow importing the sign path code.
        if (
            node.module == "homeassistant.components.http.auth"
            and len(node.names) == 1
            and node.names[0].name == "async_sign_path"
        ):
            return

        if node.module.startswith("homeassistant.components."):
            # from homeassistant.components.alexa.smart_home import EVENT_ALEXA_SMART_HOME
            # from homeassistant.components.logbook import bla
            self._add_reference(node.module.split(".")[2])

        elif node.module == "homeassistant.components":
            # from homeassistant.components import sun
            for name_node in node.names:
                self._add_reference(name_node.name)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit Import node."""
        # import homeassistant.components.hue as hue
        for name_node in node.names:
            if name_node.name.startswith("homeassistant.components."):
                self._add_reference(name_node.name.split(".")[2])

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Visit Attribute node."""
        # hass.components.hue.async_create()
        # Name(id=hass)
        #   .Attribute(attr=hue)
        #   .Attribute(attr=async_create)

        # self.hass.components.hue.async_create()
        # Name(id=self)
        #   .Attribute(attr=hass) or .Attribute(attr=_hass)
        #   .Attribute(attr=hue)
        #   .Attribute(attr=async_create)
        if (
            isinstance(node.value, ast.Attribute)
            and node.value.attr == "components"
            and (
                (
                    isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "hass"
                )
                or (
                    isinstance(node.value.value, ast.Attribute)
                    and node.value.value.attr in ("hass", "_hass")
                )
            )
        ):
            self._add_reference(node.attr)
        else:
            # Have it visit other kids
            self.generic_visit(node)


ALLOWED_USED_COMPONENTS = {
    *{platform.value for platform in Platform},
    # Internal integrations
    "alert",
    "automation",
    "conversation",
    "device_automation",
    "frontend",
    "group",
    "hassio",
    "homeassistant",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "media_source",
    "onboarding",
    "persistent_notification",
    "person",
    "script",
    "shopping_list",
    "sun",
    "system_health",
    "system_log",
    "timer",
    "webhook",
    "websocket_api",
    "zone",
    # Other
    "mjpeg",  # base class, has no reqs or component to load.
    "stream",  # Stream cannot install on all systems, can be imported without reqs.
}

IGNORE_VIOLATIONS = {
    # Has same requirement, gets defaults.
    ("sql", "recorder"),
    # Sharing a base class
    ("openalpr_cloud", "openalpr_local"),
    ("lutron_caseta", "lutron"),
    ("ffmpeg_noise", "ffmpeg_motion"),
    # Demo
    ("demo", "manual"),
    ("demo", "openalpr_local"),
    # This would be a circular dep
    ("http", "network"),
    # This should become a helper method that integrations can submit data to
    ("websocket_api", "lovelace"),
    ("websocket_api", "shopping_list"),
    "logbook",
    # Migration wizard from zwave to zwave_js.
    "zwave_js",
}


def calc_allowed_references(integration: Integration) -> set[str]:
    """Return a set of allowed references."""
    manifest = integration.manifest
    allowed_references = (
        ALLOWED_USED_COMPONENTS
        | set(manifest.get("dependencies", []))
        | set(manifest.get("after_dependencies", []))
    )
    # bluetooth_adapters is a wrapper to ensure
    # that all the integrations that provide bluetooth
    # adapters are setup before loading integrations
    # that use them.
    if "bluetooth_adapters" in allowed_references:
        allowed_references.add("bluetooth")

    # Discovery requirements are ok if referenced in manifest
    for check_domain, to_check in DISCOVERY_INTEGRATIONS.items():
        if any(check in manifest for check in to_check):
            allowed_references.add(check_domain)

    return allowed_references


def find_non_referenced_integrations(
    integrations: dict[str, Integration],
    integration: Integration,
    references: dict[Path, set[str]],
) -> set[str]:
    """Find integrations that are not allowed to be referenced."""
    allowed_references = calc_allowed_references(integration)
    referenced = set()
    for path, refs in references.items():
        if len(path.parts) == 1:
            # climate.py is stored as climate
            cur_fil_dir = path.stem
        else:
            # climate/__init__.py is stored as climate
            cur_fil_dir = path.parts[0]

        is_platform_other_integration = cur_fil_dir in integrations

        for ref in refs:
            # We are always allowed to import from ourselves
            if ref == integration.domain:
                continue

            # These references are approved based on the manifest
            if ref in allowed_references:
                continue

            # Some violations are whitelisted
            if (integration.domain, ref) in IGNORE_VIOLATIONS:
                continue

            # If it's a platform for another integration, the other integration is ok
            if is_platform_other_integration and cur_fil_dir == ref:
                continue

            # These have a platform specified in this integration
            if not is_platform_other_integration and (
                (integration.path / f"{ref}.py").is_file()
                # Platform dir
                or (integration.path / ref).is_dir()
            ):
                continue

            referenced.add(ref)

    return referenced


def validate_dependencies(
    integrations: dict[str, Integration],
    integration: Integration,
) -> None:
    """Validate all dependencies."""
    # Some integrations are allowed to have violations.
    if integration.domain in IGNORE_VIOLATIONS:
        return

    # Find usage of hass.components
    collector = ImportCollector(integration)
    collector.collect()

    for domain in sorted(
        find_non_referenced_integrations(
            integrations, integration, collector.referenced
        )
    ):
        integration.add_error(
            "dependencies",
            f"Using component {domain} but it's not in 'dependencies' "
            "or 'after_dependencies'",
        )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle dependencies for integrations."""
    # check for non-existing dependencies
    for integration in integrations.values():
        validate_dependencies(integrations, integration)

        if config.specific_integrations:
            continue

        # check that all referenced dependencies exist
        after_deps = integration.manifest.get("after_dependencies", [])
        for dep in integration.manifest.get("dependencies", []):
            if dep in after_deps:
                integration.add_error(
                    "dependencies",
                    f"Dependency {dep} is both in dependencies and after_dependencies",
                )

            if dep not in integrations:
                integration.add_error(
                    "dependencies", f"Dependency {dep} does not exist"
                )
