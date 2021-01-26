"""Tests for the EBUS config flow."""
from unittest.mock import MagicMock

from homeassistant import data_entry_flow
from homeassistant.components.ebus.const import API, CONF_MSGDEFCODES, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.typing import HomeAssistantType

from .const import HOST, INVALID_HOST, MSGDEFCODES, PORT


async def test_user_empty(hass: HomeAssistantType, ebus: MagicMock):
    """Test user config start."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_invalid_port(hass: HomeAssistantType, ebus: MagicMock):
    """Test user config with invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: INVALID_HOST,
            CONF_PORT: PORT,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"host": "invalid_host"}


async def test_user_success(hass: HomeAssistantType, ebus: MagicMock):
    """Test user config with succeed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == f"{HOST}:{PORT}"
    assert result["title"] == f"EBUS {HOST}:{PORT}"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT
    assert result["data"][CONF_MSGDEFCODES] == MSGDEFCODES

    entries = hass.config_entries.async_entries()
    config_entry = entries[0]
    assert config_entry.unique_id == f"{HOST}:{PORT}"
    api = hass.data[DOMAIN][config_entry.entry_id][API]
    assert api.ebus.ident == f"{HOST}:{PORT}"
    assert api.ebus.host == HOST
    assert api.ebus.port == PORT

    # test abort on already configured
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
