"""Enforce that the integration implements config flow.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow/
"""

from script.hassfest.model import Integration


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration implements config flow."""

    if not integration.config_flow:
        return [
            "Integration does not set config_flow in its manifest "
            f"homeassistant/components/{integration.domain}/manifest.json",
        ]

    config_flow_file = integration.path / "config_flow.py"
    if not config_flow_file.exists():
        return [
            "Integration does not implement config flow (is missing config_flow.py)",
        ]

    return None
