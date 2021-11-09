"""HALO Home integration config flow tests."""
from unittest.mock import patch

import halohome

from homeassistant import config_entries
from homeassistant.components.halohome.const import CONF_LOCATIONS, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_ABORT, RESULT_TYPE_CREATE_ENTRY

from tests.common import MockConfigEntry

HOST = "http://127.0.0.1"
MODULE = "homeassistant.components.halohome"
USERNAME = "example@example.com"
TITLE = f"HALO Home ({USERNAME})"
PASSWORD = "TestPassword"

LOCATIONS = [
    {
        "location_id": "12345",
        "passphrase": "abc123==",
        "devices": [
            {
                "device_id": 0,
                "pid": "abc123",
                "device_name": "Living Room 1",
                "mac_address": "9C:A4:6C:CC:5D:04",
            }
        ],
    }
]
USER_INPUT = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_HOST: HOST,
}
CONFIG_ENTRY = {
    **USER_INPUT,
    CONF_LOCATIONS: LOCATIONS,
}


def _patch_list(raise_error: bool = False):
    async def _list(email: str, password: str, host: str):
        if raise_error:
            raise halohome.HaloHomeError("Test login error")

        return LOCATIONS

    return patch("halohome.list_devices", new=_list)


async def test_manual_setup(hass: HomeAssistant):
    """Test successful configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_list(), patch(
        f"{MODULE}.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == CONFIG_ENTRY
    assert result["title"] == TITLE
    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_setup_already_exists(hass: HomeAssistant):
    """Test configuration flow when already setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_ENTRY,
        unique_id=USERNAME,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_list():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_manual_setup_connection_exception(hass: HomeAssistant):
    """Test configuration flow with a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert not result["errors"]

    with _patch_list(raise_error=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
