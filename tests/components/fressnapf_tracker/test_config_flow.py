"""Test the Fressnapf Tracker config flow."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

from fressnapftracker import (
    FressnapfTrackerInvalidPhoneNumberError,
    FressnapfTrackerInvalidTokenError,
    SmsCodeResponse,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.fressnapf_tracker.const import (
    CONF_PHONE_NUMBER,
    CONF_SMS_CODE,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_ACCESS_TOKEN, MOCK_PHONE_NUMBER, MOCK_USER_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_auth_client")
async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    # Submit phone number
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms_code"

    # Submit SMS code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "0123456"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_PHONE_NUMBER
    assert result["data"] == {
        CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER,
        CONF_USER_ID: MOCK_USER_ID,
        CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
    }
    assert result["context"]["unique_id"] == str(MOCK_USER_ID)
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (FressnapfTrackerInvalidPhoneNumberError, "invalid_phone_number"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_request_sms_code_errors(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test user flow with errors."""
    mock_auth_client.request_sms_code.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: "invalid"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    # Recover from error
    mock_auth_client.request_sms_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms_code"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "0123456"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (FressnapfTrackerInvalidTokenError, "invalid_sms_code"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_verify_phone_number_errors(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test user flow with invalid SMS code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms_code"

    mock_auth_client.verify_phone_number.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "999999"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms_code"
    assert result["errors"] == {"base": error}

    # Recover from error
    mock_auth_client.verify_phone_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "0123456"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_auth_client")
async def test_user_flow_duplicate_user_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts on duplicate user_id."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: f"{MOCK_PHONE_NUMBER}123"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_auth_client")
async def test_user_flow_duplicate_phone_number(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts on duplicate phone number."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("flow_starter", "expected_step_id", "expected_sms_step_id", "expected_reason"),
    [
        (
            lambda entry, hass: entry.start_reauth_flow(hass),
            "reauth_confirm",
            "reauth_sms_code",
            "reauth_successful",
        ),
        (
            lambda entry, hass: entry.start_reconfigure_flow(hass),
            "reconfigure",
            "reconfigure_sms_code",
            "reconfigure_successful",
        ),
    ],
)
@pytest.mark.usefixtures(
    "mock_api_client_init", "mock_api_client_coordinator", "mock_auth_client"
)
async def test_reauth_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    flow_starter: Callable,
    expected_step_id: str,
    expected_sms_step_id: str,
    expected_reason: str,
) -> None:
    """Test the reauth and reconfigure flows."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await flow_starter(mock_config_entry, hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step_id

    # Submit phone number
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_sms_step_id

    # Submit SMS code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "0123456"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize(
    ("flow_starter", "expected_step_id", "expected_sms_step_id", "expected_reason"),
    [
        (
            lambda entry, hass: entry.start_reauth_flow(hass),
            "reauth_confirm",
            "reauth_sms_code",
            "reauth_successful",
        ),
        (
            lambda entry, hass: entry.start_reconfigure_flow(hass),
            "reconfigure",
            "reconfigure_sms_code",
            "reconfigure_successful",
        ),
    ],
)
@pytest.mark.usefixtures("mock_api_client_init", "mock_api_client_coordinator")
async def test_reauth_reconfigure_flow_invalid_phone_number(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    flow_starter: Callable,
    expected_step_id: str,
    expected_sms_step_id: str,
    expected_reason: str,
) -> None:
    """Test reauth and reconfigure flows with invalid phone number."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await flow_starter(mock_config_entry, hass)

    mock_auth_client.request_sms_code.side_effect = (
        FressnapfTrackerInvalidPhoneNumberError
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: "invalid"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step_id
    assert result["errors"] == {"base": "invalid_phone_number"}

    # Recover from error
    mock_auth_client.request_sms_code.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_sms_step_id

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "0123456"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize(
    ("flow_starter", "expected_sms_step_id", "expected_reason"),
    [
        (
            lambda entry, hass: entry.start_reauth_flow(hass),
            "reauth_sms_code",
            "reauth_successful",
        ),
        (
            lambda entry, hass: entry.start_reconfigure_flow(hass),
            "reconfigure_sms_code",
            "reconfigure_successful",
        ),
    ],
)
@pytest.mark.usefixtures("mock_api_client_init", "mock_api_client_coordinator")
async def test_reauth_reconfigure_flow_invalid_sms_code(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    flow_starter: Callable,
    expected_sms_step_id: str,
    expected_reason: str,
) -> None:
    """Test reauth and reconfigure flows with invalid SMS code."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await flow_starter(mock_config_entry, hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )

    mock_auth_client.verify_phone_number.side_effect = FressnapfTrackerInvalidTokenError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "999999"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_sms_step_id
    assert result["errors"] == {"base": "invalid_sms_code"}

    # Recover from error
    mock_auth_client.verify_phone_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "0123456"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize(
    ("flow_starter", "expected_step_id", "expected_sms_step_id", "expected_reason"),
    [
        (
            lambda entry, hass: entry.start_reauth_flow(hass),
            "reauth_confirm",
            "reauth_sms_code",
            "reauth_successful",
        ),
        (
            lambda entry, hass: entry.start_reconfigure_flow(hass),
            "reconfigure",
            "reconfigure_sms_code",
            "reconfigure_successful",
        ),
    ],
)
@pytest.mark.usefixtures("mock_api_client_init", "mock_api_client_coordinator")
async def test_reauth_reconfigure_flow_invalid_user_id(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    flow_starter: Callable,
    expected_step_id: str,
    expected_sms_step_id: str,
    expected_reason: str,
) -> None:
    """Test reauth and reconfigure flows do not allow changing to another account."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await flow_starter(mock_config_entry, hass)

    mock_auth_client.request_sms_code = AsyncMock(
        return_value=SmsCodeResponse(id=MOCK_USER_ID + 1)
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: f"{MOCK_PHONE_NUMBER}123"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_step_id
    assert result["errors"] == {"base": "account_change_not_allowed"}

    # Recover from error
    mock_auth_client.request_sms_code = AsyncMock(
        return_value=SmsCodeResponse(id=MOCK_USER_ID)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == expected_sms_step_id

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: "0123456"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
