"""Test the Monarch Money config flow."""

from unittest.mock import AsyncMock, Mock, call, patch

from aiohttp import ClientResponseError
from gql.transport.exceptions import TransportError, TransportServerError
from monarchmoney import LoginFailedException, RequireMFAException
import pytest

from homeassistant.components.monarch_money.const import CONF_MFA_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_simple(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_api: AsyncMock
) -> None:
    """Test simple case (no MFA / no errors)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Monarch Money"
    assert result["data"] == {
        CONF_TOKEN: "mocked_token",
    }
    assert result["result"].unique_id == "222260252323873333"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_add_duplicate_entry(
    hass: HomeAssistant, mock_config_entry, mock_config_api: AsyncMock
) -> None:
    """Test a duplicate error config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("api_error", "expected_error"),
    [
        pytest.param(
            LoginFailedException("invalid credentials"),
            "invalid_auth",
            id="login_failed",
        ),
        pytest.param(
            ClientResponseError(None, (), status=401),
            "invalid_auth",
            id="client_unauthorized",
        ),
        pytest.param(
            TransportServerError("forbidden", code=403),
            "invalid_auth",
            id="transport_forbidden",
        ),
        pytest.param(
            ClientResponseError(None, (), status=500),
            "cannot_connect",
            id="client_server_error",
        ),
        pytest.param(
            TransportServerError("server error", code=500),
            "cannot_connect",
            id="transport_server_error",
        ),
    ],
)
async def test_form_login_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_api: AsyncMock,
    api_error: Exception,
    expected_error: str,
) -> None:
    """Test config flow login errors and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_config_api.return_value.login.side_effect = api_error

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_config_api.return_value.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Monarch Money"
    assert result["data"] == {
        CONF_TOKEN: "mocked_token",
    }
    assert result["context"]["unique_id"] == "222260252323873333"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("subscription_id", "expected_reason", "expected_token", "reload_count"),
    [
        pytest.param(
            "222260252323873333",
            "reauth_successful",
            "mocked_token",
            1,
            id="same_account",
        ),
        pytest.param(
            "different-subscription",
            "unique_id_mismatch",
            "fake_token_of_doom",
            0,
            id="different_account",
        ),
    ],
)
async def test_reauth_account_validation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    subscription_id: str,
    expected_reason: str,
    expected_token: str,
    reload_count: int,
) -> None:
    """Test reauthentication only updates the matching existing entry."""
    mock_config_entry.add_to_hass(hass)
    entry_id = mock_config_entry.entry_id
    mock_config_api.return_value.get_subscription_details.return_value = Mock(
        id=subscription_id
    )

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock(return_value=True)
    ) as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
    assert mock_config_entry.entry_id == entry_id
    assert mock_config_entry.unique_id == "222260252323873333"
    assert mock_config_entry.data == {CONF_TOKEN: expected_token}
    assert mock_reload.await_args_list == [call(entry_id)] * reload_count


async def test_reauth_mfa_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test an MFA reauthentication can recover from code and connection errors."""
    mock_config_entry.add_to_hass(hass)
    client = mock_config_api.return_value
    client.login.side_effect = RequireMFAException("mfa_required")

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "mfa_required"}
    assert CONF_MFA_CODE in result["data_schema"].schema

    client.multi_factor_authenticate.side_effect = LoginFailedException("bad code")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MFA_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "bad_mfa"}
    assert CONF_MFA_CODE in result["data_schema"].schema

    client.multi_factor_authenticate.side_effect = TransportError("offline")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MFA_CODE: "654321"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert CONF_MFA_CODE in result["data_schema"].schema

    client.multi_factor_authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_MFA_CODE: "654321"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    client.multi_factor_authenticate.assert_awaited_with(
        "test-username", "test-password", "654321"
    )


async def test_reauth_subscription_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test an auth failure after login returns to the credential form."""
    mock_config_entry.add_to_hass(hass)
    client = mock_config_api.return_value
    client.get_subscription_details.side_effect = LoginFailedException("expired")

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert CONF_EMAIL in result["data_schema"].schema
    assert CONF_PASSWORD in result["data_schema"].schema


async def test_form_mfa(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_api: AsyncMock
) -> None:
    """Test MFA enabled on account configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Change the login mock to raise an MFA required error
    mock_config_api.return_value.login.side_effect = RequireMFAException("mfa_required")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "mfa_required"}
    assert result["step_id"] == "user"

    # Add a bad MFA Code response
    mock_config_api.return_value.multi_factor_authenticate.side_effect = (
        LoginFailedException("Bad MFA code")
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MFA_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "bad_mfa"}
    assert result["step_id"] == "user"

    # Use a good MFA Code - Clear mock
    mock_config_api.return_value.multi_factor_authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MFA_CODE: "123456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Monarch Money"
    assert result["data"] == {
        CONF_TOKEN: "mocked_token",
    }
    assert result["result"].unique_id == "222260252323873333"

    assert len(mock_setup_entry.mock_calls) == 1
