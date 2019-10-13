"""Tests for the Growatt server config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.growatt_server import config_flow
from homeassistant.components.growatt_server.const import CONF_PLANT_ID, DEFAULT_NAME
from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_PASSWORD

FIXTURE_USER_INPUT = {
    CONF_NAME: DEFAULT_NAME,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
}

GROWATT_PLANT_LIST_RESPONSE = {
    "data": [
        {
            "plantMoneyText": "474.9 (€)",
            "plantName": "Plant name",
            "plantId": "123456",
            "isHaveStorage": "false",
            "todayEnergy": "2.6 kWh",
            "totalEnergy": "2.37 MWh",
            "currentPower": "628.8 W",
        }
    ],
    "totalData": {
        "currentPowerSum": "628.8 W",
        "CO2Sum": "2.37 KT",
        "isHaveStorage": "false",
        "eTotalMoneyText": "474.9 (€)",
        "todayEnergySum": "2.6 kWh",
        "totalEnergySum": "2.37 MWh",
    },
    "success": True,
}
GROWATT_LOGIN_RESPONSE = {"userId": 123456, "userLevel": 1, "success": True}


async def test_show_authenticate_form(hass):
    """Test that the setup form is served."""
    flow = config_flow.GrowattServerConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"


async def test_incorrect_username(hass):
    """Test that it shows the appropriate error when an incorrect username is entered."""
    flow = config_flow.GrowattServerConfigFlow()
    flow.hass = hass
    with patch(
        "growattServer.GrowattApi.login",
        return_value={"errCode": "102", "success": False},
    ):
        result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)
        assert result["errors"] == {"base": "auth_error"}


async def test_entered_plant_id(hass):
    """Test registering an integration and finishing flow with an entered plant_id."""
    flow = config_flow.GrowattServerConfigFlow()
    flow.hass = hass
    user_input = FIXTURE_USER_INPUT
    user_input[CONF_PLANT_ID] = "123456"

    with patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE):
        with patch(
            "growattServer.GrowattApi.plant_list",
            return_value=GROWATT_PLANT_LIST_RESPONSE,
        ):
            result = await flow.async_step_user(user_input=None)
            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "init"

            result = await flow.async_step_user(user_input=user_input)
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == FIXTURE_USER_INPUT[CONF_NAME]
            assert result["data"][CONF_NAME] == FIXTURE_USER_INPUT[CONF_NAME]
            assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
            assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]


async def test_full_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    flow = config_flow.GrowattServerConfigFlow()
    flow.hass = hass
    with patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE):
        with patch(
            "growattServer.GrowattApi.plant_list",
            return_value=GROWATT_PLANT_LIST_RESPONSE,
        ):
            result = await flow.async_step_user(user_input=None)
            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "init"

            result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == FIXTURE_USER_INPUT[CONF_NAME]
            assert result["data"][CONF_NAME] == FIXTURE_USER_INPUT[CONF_NAME]
            assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
            assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]


async def test_full_flow_implementation_via_init(hass):
    """Test registering an integration and finishing flow works."""
    flow = config_flow.GrowattServerConfigFlow()
    flow.hass = hass
    with patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE):
        with patch(
            "growattServer.GrowattApi.plant_list",
            return_value=GROWATT_PLANT_LIST_RESPONSE,
        ):
            result = await flow.async_step_init(user_input=None)
            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "init"

            result = await flow.async_step_init(user_input=FIXTURE_USER_INPUT)
            assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == FIXTURE_USER_INPUT[CONF_NAME]
            assert result["data"][CONF_NAME] == FIXTURE_USER_INPUT[CONF_NAME]
            assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
            assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
