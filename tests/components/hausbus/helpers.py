"""Helper functions for Haus-Bus tests."""

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


async def create_configuration(hass: HomeAssistant, flow: FlowResult) -> FlowResult:
    """Fill configuration form."""
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    return result
