"""Test the Fressnapf Tracker config flow."""

from unittest.mock import AsyncMock, MagicMock

from fressnapftracker import (
    Device,
    FressnapfTrackerInvalidPhoneNumberError,
    FressnapfTrackerInvalidTokenError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.fressnapf_tracker.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_TOKEN,
    CONF_PHONE_NUMBER,
    CONF_SERIAL_NUMBER,
    CONF_SMS_CODE,
    CONF_USER_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_ACCESS_TOKEN,
    MOCK_DEVICE_TOKEN,
    MOCK_PHONE_NUMBER,
    MOCK_SERIAL_NUMBER,
    MOCK_USER_ID,
)

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
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
        {CONF_SMS_CODE: 123456},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_PHONE_NUMBER
    assert result["data"] == {
        CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER,
        CONF_USER_ID: MOCK_USER_ID,
        CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
    }
    assert len(result["result"].subentries) == 1
    subentry = list(result["result"].subentries.values())[0]
    assert subentry.data == {
        CONF_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
        CONF_DEVICE_TOKEN: MOCK_DEVICE_TOKEN,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_invalid_phone_number(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow with invalid phone number."""
    mock_auth_client.request_sms_code.side_effect = (
        FressnapfTrackerInvalidPhoneNumberError
    )

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
    assert result["errors"] == {"base": "invalid_phone_number"}

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
        {CONF_SMS_CODE: 123456},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error_on_sms_request(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow with unknown error during SMS code request."""
    mock_auth_client.request_sms_code.side_effect = Exception("Unknown error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_user_flow_invalid_sms_code(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
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

    mock_auth_client.verify_phone_number.side_effect = FressnapfTrackerInvalidTokenError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: 999999},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms_code"
    assert result["errors"] == {"base": "invalid_sms_code"}

    # Recover from error
    mock_auth_client.verify_phone_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: 123456},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_unknown_error_on_sms_verification(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow with unknown error during SMS verification."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )

    mock_auth_client.verify_phone_number.side_effect = Exception("Unknown error")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: 123456},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sms_code"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("mock_auth_client")
async def test_user_flow_duplicate_entry(
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


@pytest.mark.usefixtures("mock_api_client")
@pytest.mark.usefixtures("mock_auth_client")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Submit phone number
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_sms_code"

    # Submit SMS code
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: 123456},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_api_client")
async def test_reconfigure_flow_invalid_phone_number(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow with invalid phone number."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_auth_client.request_sms_code.side_effect = (
        FressnapfTrackerInvalidPhoneNumberError
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: "invalid"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "invalid_phone_number"}


@pytest.mark.usefixtures("mock_api_client")
async def test_reconfigure_flow_invalid_sms_code(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow with invalid SMS code."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PHONE_NUMBER: MOCK_PHONE_NUMBER},
    )

    mock_auth_client.verify_phone_number.side_effect = FressnapfTrackerInvalidTokenError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SMS_CODE: 999999},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_sms_code"
    assert result["errors"] == {"base": "invalid_sms_code"}


@pytest.mark.usefixtures("init_integration")
async def test_subentry_flow(
    hass: HomeAssistant,
    mock_auth_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the subentry flow for adding a device."""
    # Set up a second device
    second_device = Device(serialnumber="XYZ789", token="second_token")
    mock_auth_client.get_devices.return_value = [second_device]

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_SERIAL_NUMBER: "XYZ789"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "XYZ789"
    assert result["data"] == {
        CONF_SERIAL_NUMBER: "XYZ789",
        CONF_DEVICE_TOKEN: "second_token",
    }


async def test_subentry_flow_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test subentry flow aborts when entry not loaded."""
    mock_config_entry.add_to_hass(hass)
    # Don't set up the entry - leave it NOT_LOADED

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "device"),
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
