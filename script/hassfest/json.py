"""Validate integration JSON files."""

from __future__ import annotations

import json

from .model import Config, Integration


def validate_json_files(integration: Integration) -> None:
    """Validate JSON files for integration."""
    for json_file in integration.path.glob("**/*.json"):
        if not json_file.is_file():
            continue

        try:
            json.loads(json_file.read_text())
        except json.JSONDecodeError:
            relative_path = json_file.relative_to(integration.path)
            integration.add_error("json", f"Invalid JSON file {relative_path}")


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle JSON files inside integrations."""
    if not config.specific_integrations:
        return

    for integration in integrations.values():
        validate_json_files(integration)
