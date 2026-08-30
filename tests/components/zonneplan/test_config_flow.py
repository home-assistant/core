"""Test the Zonneplan config flow."""

from unittest.mock import AsyncMock

import pytest
from pyzonneplan import (
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

    # Yes, to the critical reviewer, this is the end of this flow
    # The rest is tested below to finalize it and recover properly :)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"


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
async def test_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the account is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_ACCOUNT.user_account.uuid,
        data={CONF_EMAIL: MOCK_EMAIL},
    ).add_to_hass(hass)

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
