"""Validate dependencies."""
import pathlib
import re
from typing import Dict

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import SERVICES_SCHEMA
from homeassistant.util.yaml import load_yaml

from .model import Integration


def grep_dir(path: pathlib.Path, glob_pattern: str, search_pattern: str) -> bool:
    """Recursively go through a dir and it's children and find the regex."""
    pattern = re.compile(search_pattern)

    for fil in path.glob(glob_pattern):
        if not fil.is_file():
            continue

        if pattern.search(fil.read_text()):
            return True

    return False


def validate_services(integration: Integration):
    """Validate services."""
    # Find if integration uses services
    has_services = grep_dir(
        integration.path, "**/*.py", r"hass\.services\.(register|async_register)"
    )

    if not has_services:
        return

    try:
        data = load_yaml(str(integration.path / "services.yaml"))
    except FileNotFoundError:
        integration.add_error("services", "Registers services but has no services.yaml")
        return
    except HomeAssistantError:
        integration.add_error(
            "services", "Registers services but unable to load services.yaml"
        )
        return

    try:
        SERVICES_SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "services", "Invalid services.yaml: {}".format(humanize_error(data, err))
        )


def validate(integrations: Dict[str, Integration], config):
    """Handle dependencies for integrations."""
    # check services.yaml is cool
    for integration in integrations.values():
        if not integration.manifest:
            continue

        validate_services(integration)
