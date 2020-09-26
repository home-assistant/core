"""Test the Advantage Air config flow."""

from aiohttp import web

from homeassistant import data_entry_flow
from homeassistant.components.advantage_air import config_flow
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

API_DATA = '{"aircons":{"ac1":{"info":{"climateControlModeIsRunning":false,"countDownToOff":0,"countDownToOn":0,"fan":"high","filterCleanStatus":0,"freshAirStatus":"none","mode":"vent","myZone":0,"name":"AC","setTemp":24,"state":"off"},"zones":{"z01":{"error":0,"maxDamper":100,"measuredTemp":0,"minDamper":0,"motion":0,"motionConfig":1,"name":"Zone 1","number":1,"rssi":0,"setTemp":24,"state":"open","type":0,"value":100}}}},"system":{"hasAircons":true,"hasLights":false,"hasSensors":false,"hasThings":false,"hasThingsBOG":false,"hasThingsLight":false,"name":"testname","rid":"uniqueid","sysType":"e-zone","myAppRev":"testversion"}}'


async def api_response(request):
    """Advantage Air API response."""
    return web.Response(text=API_DATA)


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


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""

    flow = config_flow.AdvantageAirConfigFlow()
    flow.hass = hass
    user_input = {
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_PORT: 1,
    }

    result = await flow.async_step_user(user_input=user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}
