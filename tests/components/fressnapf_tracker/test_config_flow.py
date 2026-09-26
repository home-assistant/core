"""Test the Fressnapf Tracker config flow."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

from fressnapftracker import (
    FressnapfTrackerAuthenticationError,
    FressnapfTrackerConnectionError,
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
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_ACCESS_TOKEN,
    MOCK_CUSTOMER_ID,
    MOCK_EMAIL,
    MOCK_PASSWORD,
    MOCK_PHONE_NUMBER,
    MOCK_USER_ID,
)

from tests.common import MockConfigEntry

EMAIL_CREDENTIALS = {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD}


async def _start_user_flow(
    hass: HomeAssistant, auth_method: str
) -> config_entries.ConfigFlowResult:
    """Start a user flow and select an authentication method."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": auth_method}
    )


async def _start_reconfigure_flow(
    hass: HomeAssistant, entry: MockConfigEntry, auth_method: str
) -> config_entries.ConfigFlowResult:
    """Start a reconfigure flow and select an authentication method."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    assert result["menu_options"] == ["email", "sms"]
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": auth_method}
    )


async def _complete_progress_flow(
    hass: HomeAssistant, result: config_entries.ConfigFlowResult
) -> config_entries.ConfigFlowResult:
    """Wait for and continue a progress flow."""
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


async def test_user_flow_menu(hass: HomeAssistant) -> None:
    """Test the authentication method menu."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["email", "sms"]


@pytest.mark.usefixtures("mock_auth_client")
async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full user flow."""
    result = await _start_user_flow(hass, "sms")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms"
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

    result = await _start_user_flow(hass, "sms")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: "invalid"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms"
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
    result = await _start_user_flow(hass, "sms")
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

    result = await _start_user_flow(hass, "sms")
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

    result = await _start_user_flow(hass, "sms")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_email_user_flow_success(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test email authentication and automatic magic-link detection."""
    link_clicked = asyncio.Event()
    check_count = 0

    async def check_magic_link_was_clicked(access_token: str) -> bool:
        nonlocal check_count
        check_count += 1
        if check_count == 1:
            return False
        await link_clicked.wait()
        return True

    mock_auth_client.check_magic_link_was_clicked.side_effect = (
        check_magic_link_was_clicked
    )

    result = await _start_user_flow(hass, "email")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email"

    with patch(
        "homeassistant.components.fressnapf_tracker.config_flow."
        "MAGIC_LINK_POLL_INTERVAL",
        0,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], EMAIL_CREDENTIALS
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "magic_link"
        assert result["progress_action"] == "wait_for_magic_link"
        assert result["description_placeholders"] == {"email": MOCK_EMAIL}

        link_clicked.set()
        await hass.async_block_till_done()
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_EMAIL
    assert result["data"] == {
        CONF_EMAIL: MOCK_EMAIL,
        CONF_USER_ID: MOCK_USER_ID,
        CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
    }
    assert result["context"]["unique_id"] == str(MOCK_USER_ID)
    mock_auth_client.request_magic_link.assert_awaited_once_with(
        MOCK_EMAIL, MOCK_PASSWORD
    )
    assert mock_auth_client.check_magic_link_was_clicked.await_count == 2
    mock_auth_client.complete_magic_link.assert_awaited_once_with(
        MOCK_USER_ID, MOCK_ACCESS_TOKEN, MOCK_CUSTOMER_ID
    )
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            FressnapfTrackerAuthenticationError(), "invalid_auth", id="invalid-auth"
        ),
        pytest.param(
            FressnapfTrackerConnectionError(), "cannot_connect", id="cannot-connect"
        ),
        pytest.param(Exception(), "unknown", id="unknown"),
    ],
)
async def test_email_user_flow_request_errors(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test errors while requesting a magic link."""
    result = await _start_user_flow(hass, "email")
    mock_auth_client.request_magic_link.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EMAIL_CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email"
    assert result["errors"] == {"base": error}


async def test_email_user_flow_timeout(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
) -> None:
    """Test timing out while waiting for the magic link."""
    result = await _start_user_flow(hass, "email")

    with patch(
        "homeassistant.components.fressnapf_tracker.config_flow.MAGIC_LINK_TIMEOUT", 0
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], EMAIL_CREDENTIALS
        )
        result = await _complete_progress_flow(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email"
    assert result["errors"] == {"base": "magic_link_timeout"}


@pytest.mark.parametrize(
    ("method", "side_effect", "error"),
    [
        pytest.param(
            "check_magic_link_was_clicked",
            FressnapfTrackerAuthenticationError(),
            "invalid_auth",
            id="invalid-auth",
        ),
        pytest.param(
            "check_magic_link_was_clicked",
            FressnapfTrackerConnectionError(),
            "cannot_connect",
            id="cannot-connect",
        ),
        pytest.param(
            "complete_magic_link", Exception(), "unknown", id="complete-unknown"
        ),
    ],
)
async def test_email_user_flow_completion_errors(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    method: str,
    side_effect: Exception,
    error: str,
) -> None:
    """Test errors while completing email authentication."""
    result = await _start_user_flow(hass, "email")

    async def raise_error(*_: object) -> None:
        await asyncio.sleep(0)
        raise side_effect

    getattr(mock_auth_client, method).side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EMAIL_CREDENTIALS
    )
    result = await _complete_progress_flow(hass, result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email"
    assert result["errors"] == {"base": error}


async def test_email_user_flow_duplicate_email(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_email_config_entry: MockConfigEntry,
) -> None:
    """Test email authentication aborts for an already configured email."""
    mock_email_config_entry.add_to_hass(hass)
    result = await _start_user_flow(hass, "email")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EMAIL_CREDENTIALS
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_auth_client.request_magic_link.assert_not_awaited()


async def test_email_reauth_flow(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_email_config_entry: MockConfigEntry,
) -> None:
    """Test reauth for an email-authenticated entry."""
    new_access_token = "new_access_token"
    mock_auth_client.request_magic_link.return_value.user_token.access_token = (
        new_access_token
    )
    mock_email_config_entry.add_to_hass(hass)
    result = await mock_email_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EMAIL_CREDENTIALS
    )
    result = await _complete_progress_flow(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_email_config_entry.data[CONF_ACCESS_TOKEN] == new_access_token
    mock_auth_client.complete_magic_link.assert_awaited_once_with(
        MOCK_USER_ID, new_access_token, MOCK_CUSTOMER_ID
    )


async def test_reconfigure_sms_to_email(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test changing an SMS-authenticated entry to email authentication."""
    mock_config_entry.add_to_hass(hass)
    result = await _start_reconfigure_flow(hass, mock_config_entry, "email")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EMAIL_CREDENTIALS
    )
    result = await _complete_progress_flow(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.title == MOCK_EMAIL
    assert mock_config_entry.data == {
        CONF_EMAIL: MOCK_EMAIL,
        CONF_USER_ID: MOCK_USER_ID,
        CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
    }


async def test_email_reconfigure_flow(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_email_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure for an email-authenticated entry."""
    new_access_token = "new_access_token"
    mock_auth_client.request_magic_link.return_value.user_token.access_token = (
        new_access_token
    )
    mock_email_config_entry.add_to_hass(hass)
    result = await mock_email_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "email"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EMAIL_CREDENTIALS
    )
    result = await _complete_progress_flow(hass, result)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_email_config_entry.data[CONF_ACCESS_TOKEN] == new_access_token


async def test_email_reauth_account_change_not_allowed(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_email_config_entry: MockConfigEntry,
) -> None:
    """Test email reauth rejects another account."""
    mock_email_config_entry.add_to_hass(hass)
    mock_auth_client.request_magic_link.return_value.user.id = MOCK_USER_ID + 1
    result = await mock_email_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], EMAIL_CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "account_change_not_allowed"}
    mock_auth_client.complete_magic_link.assert_not_awaited()


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
            lambda entry, hass: _start_reconfigure_flow(hass, entry, "sms"),
            "sms",
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
            lambda entry, hass: _start_reconfigure_flow(hass, entry, "sms"),
            "sms",
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
            lambda entry, hass: _start_reconfigure_flow(hass, entry, "sms"),
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
            lambda entry, hass: _start_reconfigure_flow(hass, entry, "sms"),
            "sms",
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
