"""Test the Advantage Air config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.advantage_air import config_flow
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT

API_DATA = b'{"aircons":{"ac1":{"info":{"climateControlModeIsRunning":false,"countDownToOff":0,"countDownToOn":0,"fan":"high","filterCleanStatus":0,"freshAirStatus":"none","mode":"vent","myZone":0,"name":"AC","setTemp":24,"state":"off"},"zones":{"z01":{"error":0,"maxDamper":100,"measuredTemp":0,"minDamper":0,"motion":0,"motionConfig":1,"name":"Zone 1","number":1,"rssi":0,"setTemp":24,"state":"open","type":0,"value":100}}}},"system":{"hasAircons":true,"hasLights":false,"hasSensors":false,"hasThings":false,"hasThingsBOG":false,"hasThingsLight":false,"name":"testname","rid":"uniqueid","sysType":"e-zone","tspModel":"tspnumbers"}}'


async def test_form(hass, httpserver):
    """Test that form shows up."""
    flow = config_flow.AdvantageAirConfigFlow()
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_form_success(hass, httpserver):
    """Test that the setup can fully complete."""

    httpserver.serve_content(API_DATA)
    user_input = {
        CONF_IP_ADDRESS: "127.0.0.1",
        CONF_PORT: int(httpserver.url.split(":")[2]),
    }

    flow = config_flow.AdvantageAirConfigFlow()
    result = await flow.async_step_user(user_input=user_input)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "testname"
    assert result["data"][CONF_IP_ADDRESS] == user_input[CONF_IP_ADDRESS]
    assert result["data"][CONF_PORT] == user_input[CONF_PORT]


async def test_form_cannot_connect(hass, aioclient_mock):
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
