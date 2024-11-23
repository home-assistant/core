"""Enforce config_file quality scale rules.

This validates that the integration has a config flow, which is required
to set up the integration from the UI.
"""

import json

from homeassistant.generated import config_flows

from . import QualityScaleCheck


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration has a config flow."""
    flows = config_flows.FLOWS
    domains = flows["integration"]
    if check.integration.domain not in domains:
        check.add_error(
            "config_flow",
            "Integration is missing a config_flow.py, and needs to be set up with the UI",
        )

    # Validate config flow translations
    strings_file = check.integration.path / "strings.json"
    try:
        strings = json.loads(strings_file.read_text())
    except ValueError:
        # Assume that other checks will catch invalid JSON
        return

    # This assumes that all fields will have translations for field names, then
    # checks for data_description translations.
    for step, step_translations in strings.get("config", {}).get("step", {}).items():
        data_description = step_translations.get("data_description", {})
        for field in step_translations.get("data", {}):
            if field in data_description:
                continue
            check.add_error(
                "config_flow",
                f'Configuration flow step "{step}" does not give context about input field '
                f'"{field}" (is missing "data_description" in strings.json)',
            )
