"""Test the Control4 config flow."""

from unittest.mock import AsyncMock

from aiohttp.client_exceptions import ClientError
from pyControl4.error_handling import BadCredentials, NotFound, Unauthorized
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.control4.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME


async def test_full_flow(
    hass: HomeAssistant,
    mock_c4_account: AsyncMock,
    mock_c4_director: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "control4_model_00AA00AA00AA"
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        "controller_unique_id": "control4_model_00AA00AA00AA",
    }
    assert result["result"].unique_id == "00:aa:00:aa:00:aa"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (BadCredentials("Invalid username or password"), "invalid_auth"),
        (Unauthorized("Permission denied"), "invalid_auth"),
        (NotFound("something"), "controller_not_found"),
        (Exception("Some other exception"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_c4_account: AsyncMock,
    mock_c4_director: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle errors in the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_c4_account.get_account_bearer_token.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_c4_account.get_account_bearer_token.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (Unauthorized("Permission denied"), "director_auth_failed"),
        (ClientError, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (Exception("Some other exception"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_director_errors(
    hass: HomeAssistant,
    mock_c4_account: AsyncMock,
    mock_c4_director: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test we handle director auth failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_c4_director.get_all_item_info.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_c4_director.get_all_item_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_c4_account: AsyncMock,
    mock_c4_director: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate entries are not created."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_c4_director", "mock_room_variables")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_c4_account: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth flow updates the password and reloads the entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: MOCK_HOST,
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: "new-password",
        "controller_unique_id": "control4_test_123",
    }
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_c4_account.get_account_bearer_token.await_count == 3


@pytest.mark.parametrize(
    ("mock_name", "method", "exception", "error"),
    [
        pytest.param(
            "mock_c4_account",
            "get_account_bearer_token",
            BadCredentials("Invalid username or password"),
            "invalid_auth",
            id="bad_credentials",
        ),
        pytest.param(
            "mock_c4_account",
            "get_account_bearer_token",
            Unauthorized("Permission denied"),
            "invalid_auth",
            id="unauthorized",
        ),
        pytest.param(
            "mock_c4_account",
            "get_account_bearer_token",
            NotFound("something"),
            "controller_not_found",
            id="controller_not_found",
        ),
        pytest.param(
            "mock_c4_account",
            "get_account_bearer_token",
            Exception("Some other exception"),
            "unknown",
            id="account_unknown",
        ),
        pytest.param(
            "mock_c4_director",
            "get_all_item_info",
            Unauthorized("Permission denied"),
            "director_auth_failed",
            id="director_auth_failed",
        ),
        pytest.param(
            "mock_c4_director",
            "get_all_item_info",
            ClientError,
            "cannot_connect",
            id="client_error",
        ),
        pytest.param(
            "mock_c4_director",
            "get_all_item_info",
            TimeoutError,
            "cannot_connect",
            id="timeout",
        ),
        pytest.param(
            "mock_c4_director",
            "get_all_item_info",
            Exception("Some other exception"),
            "unknown",
            id="director_unknown",
        ),
    ],
)
@pytest.mark.usefixtures("mock_c4_account", "mock_c4_director")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_name: str,
    method: str,
    exception: Exception,
    error: str,
) -> None:
    """Test errors in the reauth flow and a successful retry."""
    mock_config_entry.add_to_hass(hass)
    mock_method = getattr(request.getfixturevalue(mock_name), method)
    mock_method.side_effect = exception

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_method.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_c4_director", "mock_setup_entry")
async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_c4_account: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth aborts when the account has another controller."""
    mock_config_entry.add_to_hass(hass)
    mock_c4_account.get_account_controllers.return_value = {
        "controllerCommonName": "control4_model_00BB00BB00BB",
        "href": "https://apis.control4.com/account/v3/rest/accounts/000000",
        "name": "Name",
    }

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_PASSWORD] == MOCK_PASSWORD
