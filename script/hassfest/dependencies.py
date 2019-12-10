"""Validate dependencies."""
import pathlib
import re
from typing import Dict, Set

from homeassistant.requirements import DISCOVERY_INTEGRATIONS

from .model import Integration


def grep_dir(path: pathlib.Path, glob_pattern: str, search_pattern: str) -> Set[str]:
    """Recursively go through a dir and it's children and find the regex."""
    pattern = re.compile(search_pattern)
    found = set()

    for fil in path.glob(glob_pattern):
        if not fil.is_file():
            continue

        for match in pattern.finditer(fil.read_text()):
            integration = match.groups()[1]

            if (
                # If it's importing something from itself
                integration == path.name
                # Platform file
                or (path / f"{integration}.py").exists()
                # Dir for platform
                or (path / integration).exists()
            ):
                continue

            found.add(match.groups()[1])

    return found


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
    referenced = grep_dir(
        integration.path, "**/*.py", r"(hass|homeassistant)\.components\.(\w+)"
    )
    referenced -= ALLOWED_USED_COMPONENTS
    referenced -= set(integration.manifest["dependencies"])
    referenced -= set(integration.manifest.get("after_dependencies", []))

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
