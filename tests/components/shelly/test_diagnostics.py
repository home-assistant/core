"""The scene tests for the myq platform."""
from aiohttp import ClientSession

from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.shelly.const import DOMAIN
from homeassistant.components.shelly.diagnostics import TO_REDACT
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry

RELAY_BLOCK_ID = 0


async def test_block_config_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSession, coap_wrapper
):
    """Test config entry diagnostics for block device."""
    assert coap_wrapper

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry_dict = entry.as_dict()
    entry_dict["data"].update(
        {key: REDACTED for key in TO_REDACT if key in entry_dict["data"]}
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == {
        "entry": entry_dict,
        "device_info": {
            "name": coap_wrapper.name,
            "model": coap_wrapper.model,
            "sw_version": coap_wrapper.sw_version,
        },
        "device_settings": {"coiot": {"update_period": 15}},
        "device_status": {
            "update": {
                "beta_version": "some_beta_version",
                "has_update": True,
                "new_version": "some_new_version",
                "old_version": "some_old_version",
                "status": "pending",
            }
        },
    }


async def test_rpc_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    rpc_wrapper,
):
    """Test config entry diagnostics for rpc device."""
    assert rpc_wrapper

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry_dict = entry.as_dict()
    entry_dict["data"].update(
        {key: REDACTED for key in TO_REDACT if key in entry_dict["data"]}
    )

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == {
        "entry": entry_dict,
        "device_info": {
            "name": rpc_wrapper.name,
            "model": rpc_wrapper.model,
            "sw_version": rpc_wrapper.sw_version,
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
