"""Helper functions for Haus-Bus tests."""

from homeassistant.components.hausbus.const import DOMAIN as HAUSBUS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from tests.common import MockConfigEntry

BRIDGEID = "01234E56789A"
HOST = "1.2.3.4"

HAUSBUS_CONFIG = {
    "bridgeid": BRIDGEID,
    "ipaddress": HOST,
    "mac": "00:11:22:33:44:55",
    "modelid": "hausbus",
    "name": "hausbus mock gateway",
    "sw_version": "2.05.69",
    "uuid": "1234",
}


async def create_configuration(hass: HomeAssistant, flow: FlowResult) -> FlowResult:
    """Fill configuration form."""
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    return result


async def setup_hausbus_integration(hass: HomeAssistant, *, entry_id="1"):
    """Create the deCONZ gateway."""
    config_entry = MockConfigEntry(
        domain=HAUSBUS_DOMAIN,
        entry_id=entry_id,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
