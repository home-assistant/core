"""Test the Advantage Air config flow."""

import aiohttp

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.advantage_air import config_flow
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from .common import AdvantageAirEmulator

from tests.async_mock import patch
from tests.test_util.aiohttp import AiohttpClientMocker

USER_INPUT = {
    CONF_IP_ADDRESS: "127.0.0.1",
    CONF_PORT: 2025,
}


async def test_setup_form(hass, aioclient_mock):
    """Test that the setup form is served."""
    # emulator = AdvantageAirEmulator(USER_INPUT[CONF_PORT])
    print("server running")
    flow = config_flow.AdvantageAirConfigFlow()
    flow.hass = hass
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # result = await flow.async_step_user(user_input=USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.advantage_air.config_flow.AdvantageAirConfigFlow.async_step_user",
        return_value=True,
    ), patch(
        "homeassistant.components.advantage_air.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.advantage_air.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Name of the device"
    assert result2["data"] == USER_INPUT
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    print("trying to stop")
    # emulator.stop()


async def test_form_cannot_connect(hass, aioclient_mock):
    """Test we handle cannot connect error."""

    flow = config_flow.AdvantageAirConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}


async def test_form_success(hass, aioclient_mock):
    """Test we handle cannot connect error."""

    flow = config_flow.AdvantageAirConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
