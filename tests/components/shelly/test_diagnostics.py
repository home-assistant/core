"""Tests for Shelly diagnostics platform."""
from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.shelly.diagnostics import TO_REDACT
from homeassistant.core import HomeAssistant

from . import init_integration
from .conftest import MOCK_STATUS_COAP

from tests.components.diagnostics import get_diagnostics_for_config_entry

RELAY_BLOCK_ID = 0


async def test_block_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession, mock_block_device
):
    """Test config entry diagnostics for block device."""
    await init_integration(hass, 1)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry_dict = entry.as_dict()
    entry_dict["data"].update(
        {key: REDACTED for key in TO_REDACT if key in entry_dict["data"]}
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == {
        "entry": entry_dict,
        "device_info": {
            "name": "Test name",
            "model": "SHSW-25",
            "sw_version": "some fw string",
        },
        "device_settings": {"coiot": {"update_period": 15}},
        "device_status": MOCK_STATUS_COAP,
    }


async def test_rpc_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    mock_rpc_device,
):
    """Test config entry diagnostics for rpc device."""
    await init_integration(hass, 2)

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry_dict = entry.as_dict()
    entry_dict["data"].update(
        {key: REDACTED for key in TO_REDACT if key in entry_dict["data"]}
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == {
        "entry": entry_dict,
        "device_info": {
            "name": "Test name",
            "model": "SHSW-25",
            "sw_version": "some fw string",
        },
        "device_settings": {},
        "device_status": {
            "sys": {
                "available_updates": {
                    "beta": {"version": "some_beta_version"},
                    "stable": {"version": "some_beta_version"},
                }
            }
        },
    }
