"""Enforce that the integration has a config flow."""

from homeassistant.generated import config_flows
from script.hassfest.model import Integration


def validate(integration: Integration) -> None:
    """Validate that the integration has a config flow."""
    flows = config_flows.FLOWS
    domains = flows["integration"]
    if integration.domain not in domains:
        integration.add_error(
            "IQS001",
            "Integration is missing a config_flow.py, and needs to be able to be set up via the UI",
        )
