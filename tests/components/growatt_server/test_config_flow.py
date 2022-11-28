"""Tests for the Growatt server config flow."""
from copy import deepcopy
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.growatt_server.const import (
    CONF_PLANT_ID,
    DEFAULT_URL,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
)
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_URL: DEFAULT_URL,
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
GROWATT_LOGIN_RESPONSE = {"user": {"id": 123456}, "userLevel": 1, "success": True}


async def test_show_authenticate_form(hass):
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_incorrect_login(hass):
    """Test that it shows the appropriate error when an incorrect username/password/server is entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "growattServer.GrowattApi.login",
        return_value={"msg": LOGIN_INVALID_AUTH_CODE, "success": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_no_plants_on_account(hass):
    """Test registering an integration and finishing flow with an entered plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = FIXTURE_USER_INPUT.copy()
    plant_list = deepcopy(GROWATT_PLANT_LIST_RESPONSE)
    plant_list["data"] = []

    with patch(
        "growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE
    ), patch("growattServer.GrowattApi.plant_list", return_value=plant_list):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] == "abort"
    assert result["reason"] == "no_plants"


async def test_multiple_plant_ids(hass):
    """Test registering an integration and finishing flow with an entered plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = FIXTURE_USER_INPUT.copy()
    plant_list = deepcopy(GROWATT_PLANT_LIST_RESPONSE)
    plant_list["data"].append(plant_list["data"][0])

    with patch(
        "growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE
    ), patch("growattServer.GrowattApi.plant_list", return_value=plant_list), patch(
        "homeassistant.components.growatt_server.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "plant"

        user_input = {CONF_PLANT_ID: "123456"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"


async def test_one_plant_on_account(hass):
    """Test registering an integration and finishing flow with an entered plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = FIXTURE_USER_INPUT.copy()

    with patch(
        "growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE
    ), patch(
        "growattServer.GrowattApi.plant_list",
        return_value=GROWATT_PLANT_LIST_RESPONSE,
    ), patch(
        "homeassistant.components.growatt_server.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"


async def test_existing_plant_configured(hass):
    """Test entering an existing plant_id."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="123456")
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = FIXTURE_USER_INPUT.copy()

    with patch(
        "growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE
    ), patch(
        "growattServer.GrowattApi.plant_list",
        return_value=GROWATT_PLANT_LIST_RESPONSE,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
