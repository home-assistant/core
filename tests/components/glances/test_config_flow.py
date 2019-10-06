"""Tests for Met.no config flow."""
from unittest.mock import patch

from tests.common import MockConfigEntry, mock_coro
from homeassistant import config_entries, setup
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.components.glances.config_flow import (
    GlancesFlowHandler,
    CannotConnect,
    WrongVersion,
    AlreadyConfigured,
)
from homeassistant.components.glances.const import DOMAIN

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
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.glances.config_flow.validate_input",
        return_value=mock_coro(),
    ), patch(
        "homeassistant.components.glances.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.glances.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEMO_USER_INPUT
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == NAME
    assert result2["data"] == DEMO_USER_INPUT

    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.glances.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEMO_USER_INPUT
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_wrong_version(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.glances.config_flow.validate_input",
        side_effect=WrongVersion,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEMO_USER_INPUT
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"version": "wrong_version"}


async def test_form_already_configured(hass):
    """Test host is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.glances.config_flow.validate_input",
        side_effect=AlreadyConfigured,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], DEMO_USER_INPUT
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"host": "already_configured"}


async def test_options(hass):
    """Test options for Glances."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=DEMO_USER_INPUT, options={CONF_SCAN_INTERVAL: 60}
    )
    flow = GlancesFlowHandler
    flow.hass = hass
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result2 = await options_flow.async_step_init({CONF_SCAN_INTERVAL: 10})
    assert result2["type"] == "create_entry"
    assert result2["data"][CONF_SCAN_INTERVAL] == 10
