# pylint: disable=redefined-outer-name
"""Tests for the Daikin config flow."""
import asyncio

from aiohttp import ClientError
from aiohttp.web_exceptions import HTTPForbidden
import pytest

from homeassistant.components.daikin import config_flow
from homeassistant.components.daikin.const import KEY_IP, KEY_MAC
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.async_mock import PropertyMock, patch
from tests.common import MockConfigEntry

MAC = "AABBCCDDEEFF"
HOST = "127.0.0.1"


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.FlowHandler()
    flow.hass = hass
    return flow


@pytest.fixture
def mock_daikin():
    """Mock pydaikin."""

    async def mock_daikin_factory(*args, **kwargs):
        """Mock the init function in pydaikin."""
        return Appliance

    with patch("homeassistant.components.daikin.config_flow.Appliance") as Appliance:
        type(Appliance).mac = PropertyMock(return_value="AABBCCDDEEFF")
        Appliance.factory.side_effect = mock_daikin_factory
        yield Appliance


async def test_user(hass, mock_daikin):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user({CONF_HOST: HOST})
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][KEY_MAC] == MAC


async def test_abort_if_already_setup(hass, mock_daikin):
    """Test we abort if Daikin is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(domain="daikin", data={KEY_MAC: MAC}).add_to_hass(hass)

    result = await flow.async_step_user({CONF_HOST: HOST})
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_import(hass, mock_daikin):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import({})
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_import({CONF_HOST: HOST})
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][KEY_MAC] == MAC


async def test_discovery(hass, mock_daikin):
    """Test discovery step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_discovery({KEY_IP: HOST, KEY_MAC: MAC})
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][KEY_MAC] == MAC


@pytest.mark.parametrize(
    "s_effect,reason",
    [
        (asyncio.TimeoutError, "device_timeout"),
        (HTTPForbidden, "forbidden"),
        (ClientError, "device_fail"),
        (Exception, "device_fail"),
    ],
)
async def test_device_abort(hass, mock_daikin, s_effect, reason):
    """Test device abort."""
    flow = init_config_flow(hass)
    mock_daikin.factory.side_effect = s_effect

    result = await flow.async_step_user({CONF_HOST: HOST})
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": reason}
    assert result["step_id"] == "user"
