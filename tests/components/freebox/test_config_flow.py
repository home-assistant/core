"""Tests for the Freebox config flow."""
import asyncio
from unittest.mock import MagicMock, patch

from aiofreepybox.exceptions import HttpRequestError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.freebox import config_flow
from homeassistant.components.freebox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

HOST = "myrouter.freeboxos.fr"
PORT = 1234


@pytest.fixture(name="connect")
def mock_controller_connect():
    """Mock a successful connection."""
    with patch(
        "homeassistant.components.freebox.config_flow.Freepybox"
    ) as service_mock:
        service_mock.return_value.open = MagicMock(return_value=asyncio.Future())
        service_mock.return_value.open.return_value.set_result(None)
        yield service_mock


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.FreeboxFlowHandler()
    flow.hass = hass
    return flow


async def test_user(hass, connect):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await flow.async_step_user({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_import(hass, connect):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_abort_if_already_setup(hass):
    """Test we abort if component is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: PORT}).add_to_hass(
        hass
    )

    # Should fail, same HOST (import)
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same HOST (flow)
    result = await flow.async_step_user({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "already_configured"}


async def test_abort_on_connection_failed(hass):
    """Test when we have errors during connection."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.freebox.config_flow.Freepybox.open",
        side_effect=HttpRequestError(),
    ):
        result = await flow.async_step_user({CONF_HOST: HOST, CONF_PORT: PORT})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "connection_failed"}
