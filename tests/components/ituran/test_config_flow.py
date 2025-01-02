"""Test the Ituran config flow."""

from unittest.mock import AsyncMock

from pyituran.exceptions import IturanApiError, IturanAuthError
import pytest

from homeassistant.components.ituran.const import (
    CONF_ID_OR_PASSPORT,
    CONF_MOBILE_ID,
    CONF_OTP,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .const import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


async def __do_successful_user_step(
    hass: HomeAssistant, result: ConfigFlowResult, mock_ituran: AsyncMock
):
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ID_OR_PASSPORT: MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT],
            CONF_PHONE_NUMBER: MOCK_CONFIG_DATA[CONF_PHONE_NUMBER],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {}

    return result


async def __do_successful_otp_step(
    hass: HomeAssistant,
    result: ConfigFlowResult,
    mock_ituran: AsyncMock,
):
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_OTP: "123456",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Ituran {MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT]}"
    assert result["data"][CONF_ID_OR_PASSPORT] == MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT]
    assert result["data"][CONF_PHONE_NUMBER] == MOCK_CONFIG_DATA[CONF_PHONE_NUMBER]
    assert result["data"][CONF_MOBILE_ID] is not None
    assert result["result"].unique_id == MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT]
    assert len(mock_ituran.is_authenticated.mock_calls) > 0
    assert len(mock_ituran.authenticate.mock_calls) > 0

    return result


async def test_full_user_flow(
    hass: HomeAssistant, mock_ituran: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await __do_successful_user_step(hass, result, mock_ituran)
    await __do_successful_otp_step(hass, result, mock_ituran)


async def test_invalid_auth(
    hass: HomeAssistant, mock_ituran: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test invalid credentials configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_ituran.request_otp.side_effect = IturanAuthError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ID_OR_PASSPORT: MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT],
            CONF_PHONE_NUMBER: MOCK_CONFIG_DATA[CONF_PHONE_NUMBER],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    mock_ituran.request_otp.side_effect = None
    result = await __do_successful_user_step(hass, result, mock_ituran)
    await __do_successful_otp_step(hass, result, mock_ituran)


async def test_invalid_otp(
    hass: HomeAssistant, mock_ituran: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test invalid OTP configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await __do_successful_user_step(hass, result, mock_ituran)

    mock_ituran.authenticate.side_effect = IturanAuthError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_OTP: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_otp"}

    mock_ituran.authenticate.side_effect = None
    await __do_successful_otp_step(hass, result, mock_ituran)


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [(IturanApiError, "cannot_connect"), (Exception, "unknown")],
)
async def test_errors(
    hass: HomeAssistant,
    mock_ituran: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test connection errors during configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_ituran.request_otp.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ID_OR_PASSPORT: MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT],
            CONF_PHONE_NUMBER: MOCK_CONFIG_DATA[CONF_PHONE_NUMBER],
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_ituran.request_otp.side_effect = None
    result = await __do_successful_user_step(hass, result, mock_ituran)

    mock_ituran.authenticate.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_OTP: "123456",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_ituran.authenticate.side_effect = None
    await __do_successful_otp_step(hass, result, mock_ituran)


async def test_already_authenticated(
    hass: HomeAssistant, mock_ituran: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test user already authenticated configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    mock_ituran.is_authenticated.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ID_OR_PASSPORT: MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT],
            CONF_PHONE_NUMBER: MOCK_CONFIG_DATA[CONF_PHONE_NUMBER],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Ituran {MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT]}"
    assert result["data"][CONF_ID_OR_PASSPORT] == MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT]
    assert result["data"][CONF_PHONE_NUMBER] == MOCK_CONFIG_DATA[CONF_PHONE_NUMBER]
    assert result["data"][CONF_MOBILE_ID] == MOCK_CONFIG_DATA[CONF_MOBILE_ID]
    assert result["result"].unique_id == MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT]


async def test_reauth(
    hass: HomeAssistant,
    mock_ituran: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthenticating."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await __do_successful_user_step(hass, result, mock_ituran)
    await __do_successful_otp_step(hass, result, mock_ituran)

    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] is None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_OTP: "123456",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
