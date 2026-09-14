"""Test the Zonneplan config flow."""

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pyzonneplan import (
    Token,
    ZonneplanConnectionError,
    ZonneplanInvalidOtpError,
    ZonneplanTimeoutError,
)

from homeassistant import config_entries
from homeassistant.components.zonneplan.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_ACCOUNT, MOCK_EMAIL, MOCK_USER_INPUT

from tests.common import MockConfigEntry

MOCK_OTHER_ACCOUNT = replace(
    MOCK_ACCOUNT,
    user_account=replace(
        MOCK_ACCOUNT.user_account, uuid="00000000-0000-4000-8000-00000000000f"
    ),
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_flow(hass: HomeAssistant, mock_zonneplan_client: AsyncMock) -> None:
    """Test the full OTP config flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    mock_zonneplan_client.async_request_otp.assert_called_once()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_ACCOUNT.user_account.full_name
    assert result["data"][CONF_EMAIL] == MOCK_ACCOUNT.user_account.email
    assert result["data"][CONF_TOKEN] == mock_zonneplan_client.token.as_dict()
    assert result["result"].unique_id == MOCK_ACCOUNT.user_account.uuid


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(ZonneplanConnectionError("offline"), "cannot_connect"),
        pytest.param(ZonneplanTimeoutError("timed out"), "timeout_connect"),
        pytest.param(Exception("unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_user_exceptions(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all user step exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_zonneplan_client.async_request_otp.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": reason}

    mock_zonneplan_client.async_request_otp.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_ACCOUNT.user_account.full_name
    assert result["data"][CONF_EMAIL] == MOCK_ACCOUNT.user_account.email
    assert result["data"][CONF_TOKEN] == mock_zonneplan_client.token.as_dict()
    assert result["result"].unique_id == MOCK_ACCOUNT.user_account.uuid


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(ZonneplanConnectionError("offline"), "cannot_connect"),
        pytest.param(ZonneplanTimeoutError("timed out"), "timeout_connect"),
        pytest.param(ZonneplanInvalidOtpError("bad otp"), "invalid_auth"),
        pytest.param(Exception("unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_step_otp_exceptions(
    hass: HomeAssistant,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all OTP step exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )
    assert result["step_id"] == "otp"

    mock_zonneplan_client.async_submit_otp.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {"base": reason}

    mock_zonneplan_client.async_submit_otp.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_ACCOUNT.user_account.full_name
    assert result["data"][CONF_EMAIL] == MOCK_ACCOUNT.user_account.email
    assert result["data"][CONF_TOKEN] == mock_zonneplan_client.token.as_dict()
    assert result["result"].unique_id == MOCK_ACCOUNT.user_account.uuid


@pytest.mark.usefixtures("mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test aborting when the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the reauthentication flow refreshes the stored token."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {
        CONF_EMAIL: MOCK_EMAIL,
        "name": mock_config_entry.title,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    mock_zonneplan_client.async_request_otp.assert_called_once()

    new_token = Token(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        expires_at=datetime(2031, 1, 1, tzinfo=UTC),
    )
    mock_zonneplan_client.async_submit_otp.return_value = new_token

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_EMAIL] == MOCK_EMAIL
    assert mock_config_entry.data[CONF_TOKEN] == new_token.as_dict()


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(ZonneplanConnectionError("offline"), "cannot_connect"),
        pytest.param(ZonneplanTimeoutError("timed out"), "timeout_connect"),
        pytest.param(Exception("unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_confirm_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all reauth confirm step exceptions."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_zonneplan_client.async_request_otp.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": reason}

    mock_zonneplan_client.async_request_otp.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test reauthenticating against a different account is aborted."""
    mock_config_entry.add_to_hass(hass)
    mock_zonneplan_client.async_get_account.return_value = MOCK_OTHER_ACCOUNT

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test the reconfigure flow refreshes the stored token."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"
    assert result["description_placeholders"] == {CONF_EMAIL: MOCK_EMAIL}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    mock_zonneplan_client.async_request_otp.assert_called_once()

    new_token = Token(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        expires_at=datetime(2031, 1, 1, tzinfo=UTC),
    )
    mock_zonneplan_client.async_submit_otp.return_value = new_token

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_EMAIL] == MOCK_EMAIL
    assert mock_config_entry.data[CONF_TOKEN] == new_token.as_dict()


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(ZonneplanConnectionError("offline"), "cannot_connect"),
        pytest.param(ZonneplanTimeoutError("timed out"), "timeout_connect"),
        pytest.param(Exception("unexpected"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_confirm_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test we handle all reconfigure confirm step exceptions."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_zonneplan_client.async_request_otp.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_confirm"
    assert result["errors"] == {"base": reason}

    mock_zonneplan_client.async_request_otp.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zonneplan_client: AsyncMock,
) -> None:
    """Test reconfiguring with a different account is aborted."""
    mock_config_entry.add_to_hass(hass)
    mock_zonneplan_client.async_get_account.return_value = MOCK_OTHER_ACCOUNT

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_USER_INPUT
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"otp": "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
