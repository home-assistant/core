"""Validate dependencies."""

from __future__ import annotations

import ast
from collections import deque
import multiprocessing
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
            try:
                self.visit(ast.parse(fil.read_text()))
            except SyntaxError as e:
                e.add_note(f"File: {fil}")
                raise
            self._cur_fil_dir = None

    def _add_reference(self, reference_domain: str) -> None:
        """Add a reference."""
        assert self._cur_fil_dir
        self.referenced[self._cur_fil_dir].add(reference_domain)

    def visit_If(self, node: ast.If) -> None:
        """Visit If node."""
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            # Ignore TYPE_CHECKING block
            return

        # Have it visit other kids
        self.generic_visit(node)

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
    "default_config",
    "device_automation",
    "frontend",
    "group",
    "homeassistant",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "media_source",
    "onboarding",
    "panel_custom",
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
    ("lutron_caseta", "lutron"),
    ("ffmpeg_noise", "ffmpeg_motion"),
    # Demo
    ("demo", "manual"),
    # This would be a circular dep
    ("http", "network"),
    ("http", "cloud"),
    # This would be a circular dep
    ("zha", "homeassistant_hardware"),
    ("zha", "homeassistant_sky_connect"),
    ("zha", "homeassistant_yellow"),
    ("homeassistant_sky_connect", "zha"),
    # This should become a helper method that integrations can submit data to
    ("websocket_api", "lovelace"),
    ("websocket_api", "shopping_list"),
    "logbook",
    # Temporary needed for migration until 2024.10
    ("conversation", "assist_pipeline"),
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


def _compute_integration_dependencies(
    integration: Integration,
) -> tuple[str, dict[Path, set[str]] | None]:
    """Compute integration dependencies."""
    # Some integrations are allowed to have violations.
    if integration.domain in IGNORE_VIOLATIONS:
        return (integration.domain, None)

    # Find usage of hass.components
    collector = ImportCollector(integration)
    collector.collect()
    return (integration.domain, collector.referenced)


def _validate_dependency_imports(
    integrations: dict[str, Integration],
) -> None:
    """Validate all dependencies."""

    # Find integration dependencies with multiprocessing
    # (because it takes some time to parse thousands of files)
    with multiprocessing.Pool() as pool:
        integration_imports = dict(
            pool.imap_unordered(
                _compute_integration_dependencies,
                integrations.values(),
                chunksize=10,
            )
        )

    for integration in integrations.values():
        referenced = integration_imports[integration.domain]
        if not referenced:  # Either ignored or has no references
            continue

        for domain in sorted(
            find_non_referenced_integrations(integrations, integration, referenced)
        ):
            integration.add_error(
                "dependencies",
                f"Using component {domain} but it's not in 'dependencies' "
                "or 'after_dependencies'",
            )


def _check_circular_deps(
    integrations: dict[str, Integration],
    start_domain: str,
    integration: Integration,
    checked: set[str],
    checking: deque[str],
) -> None:
    """Check for circular dependencies pointing at starting_domain."""

    if integration.domain in checked or integration.domain in checking:
        return

    checking.append(integration.domain)
    for domain in integration.manifest.get("dependencies", []):
        if domain == start_domain:
            integrations[start_domain].add_error(
                "dependencies",
                f"Found a circular dependency with {integration.domain} ({', '.join(checking)})",
            )
            break

        _check_circular_deps(
            integrations, start_domain, integrations[domain], checked, checking
        )
    else:
        for domain in integration.manifest.get("after_dependencies", []):
            if domain == start_domain:
                integrations[start_domain].add_error(
                    "dependencies",
                    f"Found a circular dependency with after dependencies of {integration.domain} ({', '.join(checking)})",
                )
                break

            _check_circular_deps(
                integrations, start_domain, integrations[domain], checked, checking
            )
    checked.add(integration.domain)
    checking.remove(integration.domain)


def _validate_circular_dependencies(integrations: dict[str, Integration]) -> None:
    for integration in integrations.values():
        if integration.domain in IGNORE_VIOLATIONS:
            continue

        _check_circular_deps(
            integrations, integration.domain, integration, set(), deque()
        )


def _validate_dependencies(
    integrations: dict[str, Integration],
) -> None:
    """Check that all referenced dependencies exist and are not duplicated."""
    for integration in integrations.values():
        if not integration.manifest:
            continue

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


def validate(
    integrations: dict[str, Integration],
    config: Config,
) -> None:
    """Handle dependencies for integrations."""
    _validate_dependency_imports(integrations)

    if not config.specific_integrations:
        _validate_dependencies(integrations)
        _validate_circular_dependencies(integrations)
