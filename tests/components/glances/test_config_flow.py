"""Tests for Glances config flow."""
from unittest.mock import patch

from glances_api import Glances

from homeassistant.components.glances import config_flow
from homeassistant.components.glances.const import DOMAIN
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


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.GlancesFlowHandler()
    flow.hass = hass
    return flow


async def test_form(hass):
    """Test config entry configured successfully."""
    flow = init_config_flow(hass)

    with patch("glances_api.Glances"), patch.object(
        Glances, "get_data", return_value=mock_coro()
    ):

        result = await flow.async_step_user(DEMO_USER_INPUT)

    assert result["type"] == "create_entry"
    assert result["title"] == NAME
    assert result["data"] == DEMO_USER_INPUT


async def test_form_cannot_connect(hass):
    """Test to return error if we cannot connect."""
    flow = init_config_flow(hass)

    with patch("glances_api.Glances"):
        result = await flow.async_step_user(DEMO_USER_INPUT)

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_wrong_version(hass):
    """Test to check if wrong version is entered."""
    flow = init_config_flow(hass)

    user_input = DEMO_USER_INPUT.copy()
    user_input.update(version=1)
    result = await flow.async_step_user(user_input)

    assert result["type"] == "form"
    assert result["errors"] == {"version": "wrong_version"}


async def test_form_already_configured(hass):
    """Test host is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=DEMO_USER_INPUT, options={CONF_SCAN_INTERVAL: 60}
    )
    entry.add_to_hass(hass)

    flow = init_config_flow(hass)
    result = await flow.async_step_user(DEMO_USER_INPUT)

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_options(hass):
    """Test options for Glances."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=DEMO_USER_INPUT, options={CONF_SCAN_INTERVAL: 60}
    )
    entry.add_to_hass(hass)
    flow = init_config_flow(hass)
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init({CONF_SCAN_INTERVAL: 10})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_SCAN_INTERVAL] == 10
