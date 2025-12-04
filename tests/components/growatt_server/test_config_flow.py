"""Tests for the Growatt server config flow."""

from copy import deepcopy

import growattServer
import pytest
import requests

from homeassistant import config_entries
from homeassistant.components.growatt_server.const import (
    ABORT_NO_PLANTS,
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    DEFAULT_URL,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_AUTH,
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


# Parametrized authentication form tests
@pytest.mark.parametrize(
    ("auth_type", "expected_fields"),
    [
        ("password_auth", [CONF_USERNAME, CONF_PASSWORD, CONF_URL]),
        ("token_auth", [CONF_TOKEN]),
    ],
)
async def test_auth_form_display(
    hass: HomeAssistant, auth_type: str, expected_fields: list[str]
) -> None:
    """Test that authentication forms are displayed correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select authentication method
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": auth_type}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == auth_type
    for field in expected_fields:
        assert field in result["data_schema"].schema


async def test_password_auth_incorrect_login(
    hass: HomeAssistant, mock_growatt_classic_api, mock_setup_entry
) -> None:
    """Test password authentication with incorrect credentials, then recovery."""
    # Simulate incorrect login
    mock_growatt_classic_api.login.return_value = {
        "msg": LOGIN_INVALID_AUTH_CODE,
        "success": False,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password_auth"
    assert result["errors"] == {"base": ERROR_INVALID_AUTH}

    # Test recovery - repatch for correct credentials
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    mock_growatt_classic_api.plant_list.return_value = GROWATT_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT_PASSWORD[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT_PASSWORD[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_PASSWORD


async def test_password_auth_no_plants(
    hass: HomeAssistant, mock_growatt_classic_api
) -> None:
    """Test password authentication with no plants."""
    # Repatch to return empty plants
    mock_growatt_classic_api.plant_list.return_value = {"data": []}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ABORT_NO_PLANTS


async def test_token_auth_no_plants(hass: HomeAssistant, mock_growatt_v1_api) -> None:
    """Test token authentication with no plants."""
    # Repatch to return empty plants
    mock_growatt_v1_api.plant_list.return_value = {"plants": []}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ABORT_NO_PLANTS


async def test_password_auth_single_plant(
    hass: HomeAssistant, mock_growatt_classic_api, mock_setup_entry
) -> None:
    """Test password authentication with single plant."""
    # Repatch plant_list with full plant data for config flow
    mock_growatt_classic_api.plant_list.return_value = GROWATT_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT_PASSWORD[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT_PASSWORD[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_PASSWORD
    assert result["data"][CONF_NAME] == "Plant name"
    assert result["result"].unique_id == "123456"


async def test_password_auth_multiple_plants(
    hass: HomeAssistant, mock_growatt_classic_api, mock_setup_entry
) -> None:
    """Test password authentication with multiple plants."""
    # Repatch plant_list with multiple plants
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
    mock_growatt_classic_api.plant_list.return_value = plant_list

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

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
    assert result["result"].unique_id == "123456"


# Token authentication tests


async def test_token_auth_api_error(
    hass: HomeAssistant, mock_growatt_v1_api, mock_setup_entry
) -> None:
    """Test token authentication with API error, then recovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    # Any GrowattV1ApiError during token verification should result in invalid_auth
    error = growattServer.GrowattV1ApiError("API error")
    error.error_code = 100
    mock_growatt_v1_api.plant_list.side_effect = error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token_auth"
    assert result["errors"] == {"base": ERROR_INVALID_AUTH}

    # Test recovery - reset side_effect and set normal return value
    mock_growatt_v1_api.plant_list.side_effect = None
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == FIXTURE_USER_INPUT_TOKEN[CONF_TOKEN]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_API_TOKEN


async def test_token_auth_connection_error(
    hass: HomeAssistant, mock_growatt_v1_api, mock_setup_entry
) -> None:
    """Test token authentication with network error, then recovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    # Simulate connection error on first attempt
    mock_growatt_v1_api.plant_list.side_effect = requests.exceptions.ConnectionError(
        "Network error"
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token_auth"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Test recovery - reset side_effect and set normal return value
    mock_growatt_v1_api.plant_list.side_effect = None
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == FIXTURE_USER_INPUT_TOKEN[CONF_TOKEN]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_API_TOKEN


async def test_token_auth_invalid_response(
    hass: HomeAssistant, mock_growatt_v1_api, mock_setup_entry
) -> None:
    """Test token authentication with invalid response format, then recovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    # Return invalid response format (None instead of dict with 'plants' key)
    mock_growatt_v1_api.plant_list.return_value = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token_auth"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Test recovery - set normal return value
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == FIXTURE_USER_INPUT_TOKEN[CONF_TOKEN]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_API_TOKEN


async def test_token_auth_single_plant(
    hass: HomeAssistant, mock_growatt_v1_api, mock_setup_entry
) -> None:
    """Test token authentication with single plant."""
    # Repatch plant_list with full plant data for config flow
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TOKEN] == FIXTURE_USER_INPUT_TOKEN[CONF_TOKEN]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_API_TOKEN
    assert result["data"][CONF_NAME] == "Test Plant V1"
    assert result["result"].unique_id == "123456"


async def test_token_auth_multiple_plants(
    hass: HomeAssistant, mock_growatt_v1_api, mock_setup_entry
) -> None:
    """Test token authentication with multiple plants."""
    # Repatch plant_list with multiple plants
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_MULTIPLE_PLANTS_RESPONSE

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

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
    assert result["result"].unique_id == "789012"


async def test_password_auth_existing_plant_configured(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
) -> None:
    """Test password authentication with existing plant_id."""
    # Repatch plant_list for this test
    mock_growatt_classic_api.plant_list.return_value = GROWATT_PLANT_LIST_RESPONSE

    # Use existing fixture (unique_id already matches what config flow returns)
    mock_config_entry_classic.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_token_auth_existing_plant_configured(
    hass: HomeAssistant, mock_growatt_v1_api, mock_config_entry: MockConfigEntry
) -> None:
    """Test token authentication with existing plant_id."""
    # Repatch plant_list for this test
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE

    # Use existing fixture (unique_id already matches what config flow returns)
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select token authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_password_auth_connection_error(
    hass: HomeAssistant, mock_growatt_classic_api, mock_setup_entry
) -> None:
    """Test password authentication with connection error, then recovery."""
    # Simulate connection error on first attempt
    mock_growatt_classic_api.login.side_effect = requests.exceptions.ConnectionError(
        "Connection failed"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password_auth"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Test recovery - reset side_effect and set normal return values
    mock_growatt_classic_api.login.side_effect = None
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    mock_growatt_classic_api.plant_list.return_value = GROWATT_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT_PASSWORD[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT_PASSWORD[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_PASSWORD


async def test_password_auth_invalid_response(
    hass: HomeAssistant, mock_growatt_classic_api, mock_setup_entry
) -> None:
    """Test password authentication with invalid response format, then recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    # Simulate invalid response error on first attempt
    mock_growatt_classic_api.login.side_effect = ValueError("Invalid JSON response")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "password_auth"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Test recovery - reset side_effect and set normal return values
    mock_growatt_classic_api.login.side_effect = None
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    mock_growatt_classic_api.plant_list.return_value = GROWATT_PLANT_LIST_RESPONSE

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT_PASSWORD[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT_PASSWORD[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == "123456"
    assert result["data"][CONF_AUTH_TYPE] == AUTH_PASSWORD


async def test_password_auth_plant_list_error(
    hass: HomeAssistant, mock_growatt_classic_api, mock_setup_entry
) -> None:
    """Test password authentication with plant list connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    # Login succeeds but plant_list fails
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    mock_growatt_classic_api.plant_list.side_effect = (
        requests.exceptions.ConnectionError("Connection failed")
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ERROR_CANNOT_CONNECT


async def test_password_auth_plant_list_invalid_format(
    hass: HomeAssistant, mock_growatt_classic_api, mock_setup_entry
) -> None:
    """Test password authentication with invalid plant list format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Select password authentication
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "password_auth"}
    )

    # Login succeeds but plant_list returns invalid format (missing "data" key)
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    mock_growatt_classic_api.plant_list.return_value = {"invalid": "format"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ERROR_CANNOT_CONNECT
