"""Tests for the Velbus config flow."""
from unittest.mock import AsyncMock, patch

import pytest
from velbusaio.exceptions import VelbusConnectionFailed

from homeassistant import data_entry_flow
from homeassistant.components.velbus import config_flow
from homeassistant.const import CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import PORT_SERIAL, PORT_TCP


@pytest.fixture(autouse=True)
def override_async_setup_entry() -> AsyncMock:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.velbus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="controller_connection_failed")
def mock_controller_connection_failed():
    """Mock the velbus controller with an assert."""
    with patch("velbusaio.controller.Velbus", side_effect=VelbusConnectionFailed()):
        yield


def init_config_flow(hass: HomeAssistant):
    """Init a configuration flow."""
    flow = config_flow.VelbusConfigFlow()
    flow.hass = hass
    return flow


@pytest.mark.usefixtures("controller")
async def test_user(hass: HomeAssistant):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test Serial", CONF_PORT: PORT_SERIAL}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "velbus_test_serial"
    assert result["data"][CONF_PORT] == PORT_SERIAL

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test TCP", CONF_PORT: PORT_TCP}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "velbus_test_tcp"
    assert result["data"][CONF_PORT] == PORT_TCP


@pytest.mark.usefixtures("controller_connection_failed")
async def test_user_fail(hass: HomeAssistant):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test Serial", CONF_PORT: PORT_SERIAL}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_PORT: "cannot_connect"}

    result = await flow.async_step_user(
        {CONF_NAME: "Velbus Test TCP", CONF_PORT: PORT_TCP}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_PORT: "cannot_connect"}


@pytest.mark.usefixtures("controller")
async def test_import(hass: HomeAssistant):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import({CONF_PORT: PORT_TCP})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "velbus_import"


@pytest.mark.usefixtures("config_entry")
async def test_abort_if_already_setup(hass: HomeAssistant):
    """Test we abort if Daikin is already setup."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import(
        {CONF_PORT: PORT_TCP, CONF_NAME: "velbus import test"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    result = await flow.async_step_user(
        {CONF_PORT: PORT_TCP, CONF_NAME: "velbus import test"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"port": "already_configured"}
