"""Tests for the Tami4 config flow."""
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from Tami4EdgeAPI.Tami4EdgeAPI import Device

from homeassistant import config_entries
from homeassistant.components.tami4.const import CONF_PHONE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.tami4.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_request_otp():
    """Mock request_otp."""
    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.request_otp",
        return_value=None,
    ) as mock_request_otp:
        yield mock_request_otp


@pytest.fixture
def mock_submit_otp():
    """Mock submit_otp."""
    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.submit_otp",
        return_value="refresh_token",
    ) as mock_submit_otp:
        yield mock_submit_otp


@pytest.fixture
def mock__get_devices():
    """Mock _get_devices."""

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI._get_devices",
        return_value=[
            Device(
                id=1,
                name="Drink Water!",
                connected=True,
                psn="psn",
                type="type",
                device_firmware="firmware",
            )
        ],
    ) as mock_get_devices:
        yield mock_get_devices


async def test_step_user_valid_number(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_request_otp,
    mock_submit_otp,
    mock__get_devices,
) -> None:
    """Test user step with valid phone number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+972555555555"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "otp"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"otp": "123456"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Drink Water!"
    assert "refresh_token" in result["data"]


async def test_step_user_invalid_number(
    hass: HomeAssistant,
    mock_setup_entry,
    mock_request_otp,
    mock_submit_otp,
    mock__get_devices,
) -> None:
    """Test user step with invalid phone number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PHONE: "+275123"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_phone"}
