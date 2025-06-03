"""Tests for the Tami4 config flow."""

import pytest
from Tami4EdgeAPI import exceptions

from homeassistant import config_entries
from homeassistant.components.tami4.const import CONF_PHONE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_step_user_valid_number(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_request_otp,
    mock__get_devices_metadata,
) -> None:
    """Test user step with valid phone number."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+972555555555"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {}


async def test_step_user_invalid_number(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_request_otp,
    mock__get_devices_metadata,
) -> None:
    """Test user step with invalid phone number."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+275123"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_phone"}


@pytest.mark.parametrize(
    ("mock_request_otp", "expected_error"),
    [(Exception, "unknown"), (exceptions.OTPFailedException, "cannot_connect")],
    indirect=["mock_request_otp"],
)
async def test_step_user_exception(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_request_otp,
    mock__get_devices_metadata,
    expected_error,
) -> None:
    """Test user step with exception."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+972555555555"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_step_otp_valid(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_request_otp,
    mock_submit_otp,
    mock__get_devices_metadata,
) -> None:
    """Test user step with valid phone number."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+972555555555"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"otp": "123456"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Drink Water"
    assert "refresh_token" in result["data"]


@pytest.mark.usefixtures(
    "mock_setup_entry",
    "mock_request_otp",
    "mock_submit_otp",
    "mock__get_devices_metadata_no_name",
)
async def test_step_otp_valid_device_no_name(hass: HomeAssistant) -> None:
    """Test user step with valid phone number."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+972555555555"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"otp": "123456"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tami4"
    assert "refresh_token" in result["data"]


@pytest.mark.parametrize(
    ("mock_submit_otp", "expected_error"),
    [
        (Exception, "unknown"),
        (exceptions.Tami4EdgeAPIException, "cannot_connect"),
        (exceptions.OTPFailedException, "invalid_auth"),
    ],
    indirect=["mock_submit_otp"],
)
async def test_step_otp_exception(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_request_otp,
    mock_submit_otp,
    mock__get_devices_metadata,
    expected_error,
) -> None:
    """Test user step with valid phone number."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+972555555555"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"otp": "123456"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {"base": expected_error}
