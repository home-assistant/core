"""Test the ENGIE Belgium config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aioengiebelgium import (
    EngieBeAuthenticationError,
    EngieBeCommunicationError,
    EngieBeError,
    EngieBeMfaError,
    MfaMethod,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.engie_be.const import (
    CONF_MFA_METHOD,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .conftest import EMAIL, PASSWORD, SUBJECT

USER_INPUT = {
    CONF_EMAIL: EMAIL,
    CONF_PASSWORD: PASSWORD,
    CONF_MFA_METHOD: "sms",
}


async def test_full_flow(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user config flow."""
    mock_engie_client.return_value.subject = SUBJECT
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    sentinel_session = MagicMock()
    with patch(
        "homeassistant.components.engie_be.config_flow.async_create_clientsession",
        return_value=sentinel_session,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    call_kwargs = (
        mock_engie_client.return_value.async_start_authentication.call_args.kwargs
    )
    assert call_kwargs["auth_session"] is sentinel_session
    assert call_kwargs["auth_session"] is not async_get_clientsession(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == EMAIL
    assert result["data"][CONF_EMAIL] == EMAIL
    assert result["data"]["access_token"] == "new-access-token"
    assert result["data"]["refresh_token"] == "new-refresh-token"
    assert CONF_PASSWORD not in result["data"]
    assert result["result"].unique_id == SUBJECT


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EngieBeCommunicationError("boom"), "cannot_connect"),
        (EngieBeAuthenticationError("boom"), "invalid_auth"),
        (EngieBeError("boom"), "unknown"),
    ],
)
async def test_user_step_errors(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test recoverable errors on the user step."""
    mock_engie_client.return_value.subject = SUBJECT
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_engie_client.return_value.async_start_authentication.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_engie_client.return_value.async_start_authentication.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EngieBeMfaError("bad code"), "invalid_mfa_code"),
        (EngieBeAuthenticationError("boom"), "invalid_auth"),
        (EngieBeCommunicationError("boom"), "cannot_connect"),
        (EngieBeError("boom"), "unknown"),
    ],
)
async def test_mfa_submit_errors_recovery(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_auth_flow: MagicMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test recoverable errors on the MFA submit step."""
    mock_engie_client.return_value.subject = SUBJECT
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["step_id"] == "mfa"

    mock_auth_flow.async_submit_mfa.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "000000"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"
    assert result["errors"] == {"base": error}

    mock_auth_flow.async_submit_mfa.side_effect = None
    mock_auth_flow.async_submit_mfa.return_value = ("access", "refresh")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_setup_entry.called


async def test_already_configured(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting when the JWT subject is already configured."""
    mock_engie_client.return_value.subject = SUBJECT
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=SUBJECT)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_two_accounts_get_distinct_entries(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that two distinct JWT subjects create two distinct entries."""
    other_subject = "auth0|7a3c9e21b48f5d0261af3d77"
    for subject in (SUBJECT, other_subject):
        mock_engie_client.return_value.subject = subject
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        assert result["step_id"] == "mfa"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"code": "123456"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 2
    assert {entry.unique_id for entry in entries} == {SUBJECT, other_subject}


async def test_jwt_subject_missing_shows_form_error(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that a missing JWT subject shows a form error on the MFA step."""
    mock_engie_client.return_value.subject = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_engie_client.return_value.subject = SUBJECT
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_setup_entry.called


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauthentication flow."""
    mock_engie_client.return_value.subject = SUBJECT
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"][CONF_EMAIL] == EMAIL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "mfa"
    mock_engie_client.return_value.async_start_authentication.assert_called_once()
    assert mock_engie_client.return_value.async_start_authentication.call_args.args[
        :3
    ] == (EMAIL, "new-password", MfaMethod.SMS)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_EMAIL: EMAIL,
        CONF_MFA_METHOD: "sms",
        CONF_ACCESS_TOKEN: "new-access-token",
        CONF_REFRESH_TOKEN: "new-refresh-token",
    }


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(
            EngieBeCommunicationError("boom"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(
            EngieBeAuthenticationError("boom"), "invalid_auth", id="invalid_auth"
        ),
        pytest.param(EngieBeError("boom"), "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    error: str,
) -> None:
    """Test recoverable errors in the reauthentication flow."""
    mock_engie_client.return_value.subject = SUBJECT
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_engie_client.return_value.async_start_authentication.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    mock_engie_client.return_value.async_start_authentication.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    assert result["step_id"] == "mfa"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "new-access-token"


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_engie_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication aborts when signing in to a different account."""
    mock_engie_client.return_value.subject = "auth0|7a3c9e21b48f5d0261af3d77"
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"code": "123456"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_ACCESS_TOKEN] == "access-token"
