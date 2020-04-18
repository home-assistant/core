"""Tests for Glances config flow."""
from unittest.mock import patch

from glances_api import Glances

from homeassistant import data_entry_flow
from homeassistant.components import glances
from homeassistant.const import CONF_SCAN_INTERVAL

from tests.common import MockConfigEntry, mock_coro

NAME = "Glances"
HOST = "0.0.0.0"
USERNAME = "username"
PASSWORD = "password"
PORT = 61208
VERSION = 3
SCAN_INTERVAL = 10

DEMO_USER_INPUT = {
    "name": NAME,
    "host": HOST,
    "username": USERNAME,
    "password": PASSWORD,
    "version": VERSION,
    "port": PORT,
    "ssl": False,
    "verify_ssl": True,
}


async def test_form(hass):
    """Test config entry configured successfully."""

    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch("glances_api.Glances"), patch.object(
        Glances, "get_data", return_value=mock_coro()
    ):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=DEMO_USER_INPUT
        )

    assert result["type"] == "create_entry"
    assert result["title"] == NAME
    assert result["data"] == DEMO_USER_INPUT


async def test_form_cannot_connect(hass):
    """Test to return error if we cannot connect."""

    with patch("glances_api.Glances"):
        result = await hass.config_entries.flow.async_init(
            glances.DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=DEMO_USER_INPUT
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_wrong_version(hass):
    """Test to check if wrong version is entered."""

    user_input = DEMO_USER_INPUT.copy()
    user_input.update(version=1)
    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == "form"
    assert result["errors"] == {"version": "wrong_version"}


async def test_form_already_configured(hass):
    """Test host is already configured."""
    entry = MockConfigEntry(
        domain=glances.DOMAIN, data=DEMO_USER_INPUT, options={CONF_SCAN_INTERVAL: 60}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_options(hass):
    """Test options for Glances."""
    entry = MockConfigEntry(
        domain=glances.DOMAIN, data=DEMO_USER_INPUT, options={CONF_SCAN_INTERVAL: 60}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={glances.CONF_SCAN_INTERVAL: 10}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        glances.CONF_SCAN_INTERVAL: 10,
    }
