"""Enforce that the integration implements config flow.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/config-flow/
"""

from homeassistant.generated import config_flows
from script.hassfest.model import Integration


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration implements config flow."""

    config_flow_file = integration.path / "config_flow.py"
    if not config_flow_file.exists():
        return [
            "Integration does not implement config flow (is missing config_flow.py)",
        ]

    if integration.domain not in config_flows.FLOWS["integration"]:
        return [
            "Integration is missing from homeassistant/generator/config_flow.py "
            f"(or homeassistant/components/{integration.domain}/manifest.json)",
        ]

    return None
