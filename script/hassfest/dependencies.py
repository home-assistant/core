"""Validate dependencies."""
import ast
from typing import Dict, Set

from homeassistant.requirements import DISCOVERY_INTEGRATIONS

from .model import Integration


class ImportCollector(ast.NodeVisitor):
    """Collect all integrations referenced."""

    def __init__(self, integration: Integration):
        """Initialize the import collector."""
        self.integration = integration
        self.referenced: Set[str] = set()

    def maybe_add_reference(self, reference_domain: str):
        """Add a reference."""
        if (
            # If it's importing something from itself
            reference_domain == self.integration.path.name
            # Platform file
            or (self.integration.path / f"{reference_domain}.py").exists()
            # Platform dir
            or (self.integration.path / reference_domain).exists()
        ):
            return

        self.referenced.add(reference_domain)

    def visit_ImportFrom(self, node):
        """Visit ImportFrom node."""
        if node.module is None:
            return

        if node.module.startswith("homeassistant.components."):
            # from homeassistant.components.alexa.smart_home import EVENT_ALEXA_SMART_HOME
            # from homeassistant.components.logbook import bla
            self.maybe_add_reference(node.module.split(".")[2])

        elif node.module == "homeassistant.components":
            # from homeassistant.components import sun
            for name_node in node.names:
                self.maybe_add_reference(name_node.name)

    def visit_Import(self, node):
        """Visit Import node."""
        # import homeassistant.components.hue as hue
        for name_node in node.names:
            if name_node.name.startswith("homeassistant.components."):
                self.maybe_add_reference(name_node.name.split(".")[2])

    def visit_Attribute(self, node):
        """Visit Attribute node."""
        # hass.components.hue.async_create()
        # Name(id=hass)
        #   .Attribute(attr=hue)
        #   .Attribute(attr=async_create)

        # self.hass.components.hue.async_create()
        # Name(id=self)
        #   .Attribute(attr=hass)
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
                    and node.value.value.attr == "hass"
                )
            )
        ):
            self.maybe_add_reference(node.attr)
        else:
            # Have it visit other kids
            self.generic_visit(node)


ALLOWED_USED_COMPONENTS = {
    # This component will always be set up
    "persistent_notification",
    # These allow to register things without being set up
    "conversation",
    "frontend",
    "hassio",
    "system_health",
    "websocket_api",
    "automation",
    "device_automation",
    "zone",
    "homeassistant",
    "system_log",
    "person",
    # Discovery
    "discovery",
    # Other
    "mjpeg",  # base class, has no reqs or component to load.
}

IGNORE_VIOLATIONS = [
    # Has same requirement, gets defaults.
    ("sql", "recorder"),
    # Sharing a base class
    ("openalpr_cloud", "openalpr_local"),
    ("lutron_caseta", "lutron"),
    ("ffmpeg_noise", "ffmpeg_motion"),
    # Demo
    ("demo", "manual"),
    ("demo", "openalpr_local"),
    # This should become a helper method that integrations can submit data to
    ("websocket_api", "lovelace"),
    # Expose HA to external systems
    "homekit",
    "alexa",
    "google_assistant",
    "emulated_hue",
    "prometheus",
    "conversation",
    "logbook",
    # These should be extracted to external package
    "pvoutput",
    "dwd_weather_warnings",
    # Should be rewritten to use own data fetcher
    "scrape",
]


def validate_dependencies(integration: Integration):
    """Validate all dependencies."""
    # Find usage of hass.components
    collector = ImportCollector(integration)

    for fil in integration.path.glob("**/*.py"):
        if not fil.is_file():
            continue

        collector.visit(ast.parse(fil.read_text()))

    referenced = (
        collector.referenced
        - ALLOWED_USED_COMPONENTS
        - set(integration.manifest["dependencies"])
        - set(integration.manifest.get("after_dependencies", []))
    )

    # Discovery requirements are ok if referenced in manifest
    for check_domain, to_check in DISCOVERY_INTEGRATIONS.items():
        if check_domain in referenced and any(
            check in integration.manifest for check in to_check
        ):
            referenced.remove(check_domain)

    if referenced:
        for domain in sorted(referenced):
            if (
                integration.domain in IGNORE_VIOLATIONS
                or (integration.domain, domain) in IGNORE_VIOLATIONS
            ):
                continue

            integration.add_error(
                "dependencies",
                "Using component {} but it's not in 'dependencies' or 'after_dependencies'".format(
                    domain
                ),
            )


def validate(integrations: Dict[str, Integration], config):
    """Handle dependencies for integrations."""
    # check for non-existing dependencies
    for integration in integrations.values():
        if not integration.manifest:
            continue

        validate_dependencies(integration)

        # check that all referenced dependencies exist
        for dep in integration.manifest["dependencies"]:
            if dep not in integrations:
                integration.add_error(
                    "dependencies", f"Dependency {dep} does not exist"
                )
