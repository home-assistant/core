"""Tests for the Growatt server config flow."""

from copy import deepcopy

import growattServer
import pytest
import requests
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.growatt_server.const import (
    ABORT_NO_PLANTS,
    AUTH_API_TOKEN,
    AUTH_PASSWORD,
    CONF_AUTH_TYPE,
    CONF_PLANT_ID,
    CONF_REGION,
    DEFAULT_URL,
    DOMAIN,
    ERROR_CANNOT_CONNECT,
    ERROR_INVALID_AUTH,
    LOGIN_INVALID_AUTH_CODE,
    SERVER_URLS_NAMES,
    V1_API_ERROR_NO_PRIVILEGE,
    V1_API_ERROR_RATE_LIMITED,
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
    CONF_REGION: DEFAULT_URL,
}

FIXTURE_USER_INPUT_TOKEN = {
    CONF_TOKEN: "test_api_token_12345",
    CONF_REGION: DEFAULT_URL,
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
        ("password_auth", [CONF_USERNAME, CONF_PASSWORD, CONF_REGION]),
        ("token_auth", [CONF_TOKEN, CONF_REGION]),
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


@pytest.mark.parametrize(
    ("error_code", "expected_error"),
    [
        (V1_API_ERROR_NO_PRIVILEGE, ERROR_INVALID_AUTH),
        (V1_API_ERROR_RATE_LIMITED, ERROR_CANNOT_CONNECT),
    ],
)
async def test_token_auth_api_error(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_setup_entry,
    error_code: int,
    expected_error: str,
) -> None:
    """Test token authentication with V1 API error maps to correct error type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "token_auth"}
    )

    error = growattServer.GrowattV1ApiError("API error")
    error.error_code = error_code
    mock_growatt_v1_api.plant_list.side_effect = error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token_auth"
    assert result["errors"] == {"base": expected_error}

    # Test recovery
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


# Reauthentication flow tests


@pytest.mark.parametrize(
    ("stored_url", "user_input", "expected_region"),
    [
        (
            SERVER_URLS_NAMES["other_regions"],
            FIXTURE_USER_INPUT_PASSWORD,
            "other_regions",
        ),
        (
            SERVER_URLS_NAMES["north_america"],
            {
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_REGION: "north_america",
            },
            "north_america",
        ),
    ],
)
async def test_reauth_password_success(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    snapshot: SnapshotAssertion,
    stored_url: str,
    user_input: dict,
    expected_region: str,
) -> None:
    """Test successful reauthentication with password auth for default and non-default regions."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: AUTH_PASSWORD,
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_URL: stored_url,
            CONF_PLANT_ID: "123456",
            "name": "Test Plant",
        },
        unique_id="123456",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result == snapshot(exclude=props("data_schema"))
    region_key = next(
        k
        for k in result["data_schema"].schema
        if isinstance(k, vol.Required) and k.schema == CONF_REGION
    )
    assert region_key.default() == expected_region

    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == snapshot


@pytest.mark.parametrize(
    ("login_side_effect", "login_return_value"),
    [
        (
            None,
            {"msg": LOGIN_INVALID_AUTH_CODE, "success": False},
        ),
        (
            requests.exceptions.ConnectionError("Connection failed"),
            None,
        ),
    ],
)
async def test_reauth_password_error_then_recovery(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    snapshot: SnapshotAssertion,
    login_side_effect: Exception | None,
    login_return_value: dict | None,
) -> None:
    """Test password reauth shows error then allows recovery."""
    mock_config_entry_classic.add_to_hass(hass)

    result = await mock_config_entry_classic.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_growatt_classic_api.login.side_effect = login_side_effect
    if login_return_value is not None:
        mock_growatt_classic_api.login.return_value = login_return_value
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result == snapshot(exclude=props("data_schema"))

    # Recover with correct credentials
    mock_growatt_classic_api.login.side_effect = None
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_token_success(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful reauthentication with token auth."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result == snapshot(exclude=props("data_schema"))

    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == snapshot


def _make_no_privilege_error() -> growattServer.GrowattV1ApiError:
    error = growattServer.GrowattV1ApiError("No privilege access")
    error.error_code = V1_API_ERROR_NO_PRIVILEGE
    return error


@pytest.mark.parametrize(
    "plant_list_side_effect",
    [
        _make_no_privilege_error(),
        requests.exceptions.ConnectionError("Network error"),
    ],
)
async def test_reauth_token_error_then_recovery(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    plant_list_side_effect: Exception,
) -> None:
    """Test token reauth shows error then allows recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_growatt_v1_api.plant_list.side_effect = plant_list_side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result == snapshot(exclude=props("data_schema"))

    # Recover with a valid token
    mock_growatt_v1_api.plant_list.side_effect = None
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_token_non_auth_api_error(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth token with non-auth V1 API error (e.g. rate limit) shows cannot_connect."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    error = growattServer.GrowattV1ApiError("Rate limit exceeded")
    error.error_code = V1_API_ERROR_RATE_LIMITED
    mock_growatt_v1_api.plant_list.side_effect = error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}


async def test_reauth_password_invalid_response(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
) -> None:
    """Test reauth password flow with non-dict login response, then recovery."""
    mock_config_entry_classic.add_to_hass(hass)
    result = await mock_config_entry_classic.start_reauth_flow(hass)

    mock_growatt_classic_api.login.return_value = "not_a_dict"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Recover with correct credentials
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_password_non_auth_login_failure(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reauth password flow when login fails with a non-auth error."""
    mock_config_entry_classic.add_to_hass(hass)
    result = await mock_config_entry_classic.start_reauth_flow(hass)

    mock_growatt_classic_api.login.return_value = {
        "success": False,
        "msg": "server_maintenance",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Recover with correct credentials
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry_classic.data == snapshot


async def test_reauth_password_exception(
    hass: HomeAssistant,
    mock_growatt_classic_api,
    mock_config_entry_classic: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reauth password flow with unexpected exception from login, then recovery."""
    mock_config_entry_classic.add_to_hass(hass)
    result = await mock_config_entry_classic.start_reauth_flow(hass)

    mock_growatt_classic_api.login.side_effect = ValueError("Unexpected error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Recover with correct credentials
    mock_growatt_classic_api.login.side_effect = None
    mock_growatt_classic_api.login.return_value = GROWATT_LOGIN_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_PASSWORD
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry_classic.data == snapshot


async def test_reauth_token_exception(
    hass: HomeAssistant,
    mock_growatt_v1_api,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reauth token flow with unexpected exception from plant_list, then recovery."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_growatt_v1_api.plant_list.side_effect = ValueError("Unexpected error")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    # Recover with a valid token
    mock_growatt_v1_api.plant_list.side_effect = None
    mock_growatt_v1_api.plant_list.return_value = GROWATT_V1_PLANT_LIST_RESPONSE
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], FIXTURE_USER_INPUT_TOKEN
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == snapshot


async def test_reauth_unknown_auth_type(hass: HomeAssistant) -> None:
    """Test reauth aborts immediately when the config entry has an unknown auth type."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_AUTH_TYPE: "unknown_type",
            "plant_id": "123456",
            "name": "Test Plant",
        },
        unique_id="123456",
    )
    entry.add_to_hass(hass)

    # The flow aborts immediately without showing a form
    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == ERROR_CANNOT_CONNECT
