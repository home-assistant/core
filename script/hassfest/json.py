"""Validate integration JSON files."""
import json
from typing import Dict

from .model import Integration


def validate_json_files(integration: Integration):
    """Validate JSON files for integration."""
    for json_file in integration.path.glob("**/*.json"):
        if not json_file.is_file():
            continue

        try:
            json.loads(json_file.read_text())
        except json.JSONDecodeError:
            relative_path = json_file.relative_to(integration.path)
            integration.add_error("json", f"Invalid JSON file {relative_path}")

    return


def validate(integrations: Dict[str, Integration], config):
    """Handle JSON files inside integrations."""
    if not config.specific_integrations:
        return

    for integration in integrations.values():
        if not integration.manifest:
            continue

        validate_json_files(integration)
