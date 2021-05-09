"""Tests for the Growatt server config flow."""
from copy import deepcopy
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.growatt_server.const import CONF_PLANT_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

FIXTURE_USER_INPUT = {CONF_USERNAME: "username", CONF_PASSWORD: "password"}

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_incorrect_username(hass):
    """Test that it shows the appropriate error when an incorrect username is entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "growattServer.GrowattApi.login",
        return_value={"errCode": "102", "success": False},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
        assert result2["errors"] == {"base": "invalid_auth"}


async def test_no_plants_on_account(hass):
    """Test registering an integration and finishing flow with an entered plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = FIXTURE_USER_INPUT.copy()
    plant_list = deepcopy(GROWATT_PLANT_LIST_RESPONSE)
    plant_list["data"] = []

    with patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE):
        with patch("growattServer.GrowattApi.plant_list", return_value=plant_list):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == "abort"
            assert result2["reason"] == "no_plants"


async def test_multiple_plant_ids(hass):
    """Test registering an integration and finishing flow with an entered plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = FIXTURE_USER_INPUT.copy()
    plant_list = deepcopy(GROWATT_PLANT_LIST_RESPONSE)
    plant_list["data"].append(plant_list["data"][0])

    with patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE):
        with patch("growattServer.GrowattApi.plant_list", return_value=plant_list):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result2["step_id"] == "plant"

            user_input = {CONF_PLANT_ID: "123456"}
            result3 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result3["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
            assert result3["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
            assert result3["data"][CONF_PLANT_ID] == user_input[CONF_PLANT_ID]


async def test_one_plant_on_account(hass):
    """Test registering an integration and finishing flow with an entered plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = FIXTURE_USER_INPUT.copy()

    with patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE):
        with patch(
            "growattServer.GrowattApi.plant_list",
            return_value=GROWATT_PLANT_LIST_RESPONSE,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
            assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result2["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
            assert result2["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]


async def test_full_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE):
        with patch(
            "growattServer.GrowattApi.plant_list",
            return_value=GROWATT_PLANT_LIST_RESPONSE,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
            assert result["step_id"] == "user"

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"], FIXTURE_USER_INPUT
            )
            assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
            assert result2["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
            assert result2["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
