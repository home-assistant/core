"""Test the Advantage Air config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.advantage_air import config_flow
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

from tests.components.advantage_air import api_response


async def test_form(hass):
    """Test that form shows up."""
    flow = config_flow.AdvantageAirConfigFlow()
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_form_success(hass, aiohttp_raw_server, aiohttp_unused_port):
    """Test that the setup can fully complete."""

    port = aiohttp_unused_port()
    await aiohttp_raw_server(api_response, port=port)

    user_input = {
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_PORT: port,
    }

    flow = config_flow.AdvantageAirConfigFlow()
    result = await flow.async_step_user(user_input=user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "testname"
    assert result["data"][CONF_IP_ADDRESS] == user_input[CONF_IP_ADDRESS]
    assert result["data"][CONF_PORT] == user_input[CONF_PORT]


async def test_form_cannot_connect(hass, aiohttp_unused_port):
    """Test we handle cannot connect error."""

    port = aiohttp_unused_port()

    flow = config_flow.AdvantageAirConfigFlow()
    flow.hass = hass
    user_input = {
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_PORT: port,
    }

    result = await flow.async_step_user(user_input=user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
