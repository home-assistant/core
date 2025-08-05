"""Tests for the Growatt server config flow."""

from copy import deepcopy
from unittest.mock import patch

import growattServer

from homeassistant import config_entries
from homeassistant.components.growatt_server.const import (
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_URL,
    DOMAIN,
    LOGIN_INVALID_AUTH_CODE,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT_PASSWORD = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_URL: DEFAULT_URL,
}

FIXTURE_USER_INPUT_TOKEN = {
    CONF_TOKEN: "test_api_token_12345",
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

# API token responses
GROWATT_V1_PLANT_LIST_RESPONSE = {
    "plants": [
        {
            "plant_id": 123456,
            "name": "Test Plant V1",
            "plant_uid": "test_uid_123",
        }
    ]
}

GROWATT_V1_MULTIPLE_PLANTS_RESPONSE = {
    "plants": [
        {
            "plant_id": 123456,
            "name": "Test Plant 1",
            "plant_uid": "test_uid_123",
        },
        {
            "plant_id": 789012,
            "name": "Test Plant 2",
            "plant_uid": "test_uid_789",
        },
    ]
}


# Menu navigation tests
async def test_show_auth_menu(hass: HomeAssistant) -> None:
    """Test that the authentication menu is displayed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["password_auth", "token_auth"]


# Password authentication tests
async def test_password_auth_form_display(hass: HomeAssistant) -> None:
    """Test that the password authentication form is displayed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password_auth"
    assert CONF_USERNAME in result["data_schema"].schema
    assert CONF_PASSWORD in result["data_schema"].schema
    assert CONF_URL in result["data_schema"].schema


async def test_password_auth_incorrect_login(hass: HomeAssistant) -> None:
    """Test password authentication with incorrect credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    with patch(
        "growattServer.GrowattApi.login",
        return_value={"msg": LOGIN_INVALID_AUTH_CODE, "success": False},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password_auth"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_password_auth_no_plants(hass: HomeAssistant) -> None:
    """Test password authentication with no plants on account."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    plant_list = deepcopy(GROWATT_PLANT_LIST_RESPONSE)
    plant_list["data"] = []

    with (
        patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE),
        patch("growattServer.GrowattApi.plant_list", return_value=plant_list),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_plants"


async def test_password_auth_single_plant(hass: HomeAssistant) -> None:
    """Test password authentication with single plant."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    with (
        patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE),
        patch(
            "growattServer.GrowattApi.plant_list",
            return_value=GROWATT_PLANT_LIST_RESPONSE,
        ),
        patch(
            "homeassistant.components.growatt_server.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT_PASSWORD[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT_PASSWORD[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_PASSWORD
    assert result["data"][CONF_NAME] == "Plant name"


async def test_password_auth_multiple_plants(hass: HomeAssistant) -> None:
    """Test password authentication with multiple plants."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    plant_list = deepcopy(GROWATT_PLANT_LIST_RESPONSE)
    plant_list["data"].append(
        {
            "plantMoneyText": "300.0 (€)",
            "plantName": "Plant name 2",
            "plantId": "789012",
            "isHaveStorage": "true",
            "todayEnergy": "1.5 kWh",
            "totalEnergy": "1.8 MWh",
            "currentPower": "420.0 W",
        }
    )

    with (
        patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE),
        patch("growattServer.GrowattApi.plant_list", return_value=plant_list),
        patch(
            "homeassistant.components.growatt_server.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
        )

        # Should show plant selection form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "plant"

        # Select first plant
        user_input = {CONF_PLANT_ID: "123456"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT_PASSWORD[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT_PASSWORD[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_PASSWORD


async def test_existing_plant_configured_password_auth(hass: HomeAssistant) -> None:
    """Test entering an existing plant_id with password auth."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="123456")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    with (
        patch("growattServer.GrowattApi.login", return_value=GROWATT_LOGIN_RESPONSE),
        patch(
            "growattServer.GrowattApi.plant_list",
            return_value=GROWATT_PLANT_LIST_RESPONSE,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# Token authentication tests
async def test_token_auth_form_display(hass: HomeAssistant) -> None:
    """Test that the token authentication form is displayed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token_auth"
    assert CONF_TOKEN in result["data_schema"].schema


async def test_token_auth_api_error(hass: HomeAssistant) -> None:
    """Test token authentication with any API error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    # Any GrowattV1ApiError should result in generic error
    error = growattServer.GrowattV1ApiError("Any API error")

    with patch("growattServer.OpenApiV1.plant_list", side_effect=error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_TOKEN
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token_auth"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_token_auth_no_plants(hass: HomeAssistant) -> None:
    """Test token authentication with no plants."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    with patch(
        "growattServer.OpenApiV1.plant_list",
        return_value={"plants": []},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_TOKEN
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_plants"


async def test_token_auth_single_plant(hass: HomeAssistant) -> None:
    """Test token authentication with single plant."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    with (
        patch(
            "growattServer.OpenApiV1.plant_list",
            return_value=GROWATT_V1_PLANT_LIST_RESPONSE,
        ),
        patch(
            "homeassistant.components.growatt_server.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_TOKEN
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == FIXTURE_USER_INPUT_TOKEN[CONF_TOKEN]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_API_TOKEN
    assert result["data"][CONF_NAME] == "Test Plant V1"


async def test_token_auth_multiple_plants(hass: HomeAssistant) -> None:
    """Test token authentication with multiple plants."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    with (
        patch(
            "growattServer.OpenApiV1.plant_list",
            return_value=GROWATT_V1_MULTIPLE_PLANTS_RESPONSE,
        ),
        patch(
            "homeassistant.components.growatt_server.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT_TOKEN
        )

        # Should show plant selection form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "plant"

        # Select second plant
        user_input = {CONF_PLANT_ID: "789012"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == FIXTURE_USER_INPUT_TOKEN[CONF_TOKEN]
    assert result["data"][CONF_PLANT_ID] == "789012"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_API_TOKEN
    assert result["data"][CONF_NAME] == "Test Plant 2"
