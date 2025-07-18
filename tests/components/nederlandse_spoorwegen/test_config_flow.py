"""Test config flow for Nederlandse Spoorwegen integration (new architecture)."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nederlandse_spoorwegen.api import (
    NSAPIAuthError,
    NSAPIConnectionError,
)
from homeassistant.components.nederlandse_spoorwegen.config_flow import (
    normalize_and_validate_time_format,
    validate_time_format,
)
from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

API_KEY = "abc1234567"


@pytest.mark.asyncio
async def test_config_flow_user_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.validate_api_key = AsyncMock(return_value=True)
        mock_wrapper.get_stations = AsyncMock(
            return_value=[{"code": "AMS", "name": "Amsterdam"}]
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("title") == "Nederlandse Spoorwegen"
        assert result.get("data") == {CONF_API_KEY: API_KEY}


@pytest.mark.asyncio
async def test_config_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test config flow with invalid auth."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper_cls.return_value.validate_api_key = AsyncMock(
            side_effect=NSAPIAuthError("Invalid API key")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "invalid_key"}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow with connection error."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper_cls.return_value.validate_api_key = AsyncMock(
            side_effect=NSAPIConnectionError("Cannot connect")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Test config flow aborts if already configured."""
    # Since single_config_entry is true, we should get an abort when trying to add a second
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        unique_id=API_KEY,  # Use API key as unique_id
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The flow should be aborted or show an error immediately due to single_config_entry
    # Check if it's aborted on init
    if result.get("type") == FlowResultType.ABORT:
        assert result.get("reason") in ["single_instance_allowed", "already_configured"]
    else:
        # If not aborted on init, it should be on configuration
        with patch(
            "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
        ) as mock_wrapper_cls:
            mock_wrapper = mock_wrapper_cls.return_value
            mock_wrapper.validate_api_key = AsyncMock(return_value=True)
            mock_wrapper.get_stations = AsyncMock(
                return_value=[{"code": "AMS", "name": "Amsterdam"}]
            )

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_API_KEY: API_KEY}
            )
            assert result.get("type") == FlowResultType.ABORT
            assert result.get("reason") == "already_configured"


def test_validate_time_format() -> None:
    """Test the time format validation function."""
    # Valid time formats
    assert validate_time_format("08:30:00") is True
    assert validate_time_format("23:59:59") is True
    assert validate_time_format("00:00:00") is True
    assert validate_time_format("12:30:45") is True
    assert validate_time_format("8:30:00") is True  # Single digit hour is allowed
    assert validate_time_format(None) is True  # Optional field
    assert validate_time_format("") is True  # Empty string treated as None

    # Invalid time formats
    assert validate_time_format("08:30") is True  # HH:MM format is now allowed
    assert validate_time_format("08:30:00:00") is False  # Too many parts
    assert validate_time_format("25:30:00") is False  # Invalid hour
    assert validate_time_format("08:60:00") is False  # Invalid minute
    assert validate_time_format("08:30:60") is False  # Invalid second
    assert validate_time_format("not_a_time") is False  # Invalid format
    assert validate_time_format("08-30-00") is False  # Wrong separator


def test_normalize_and_validate_time_format() -> None:
    """Test the time normalization and validation function."""
    # Test normalization from HH:MM to HH:MM:SS
    assert normalize_and_validate_time_format("08:30") == (True, "08:30:00")
    assert normalize_and_validate_time_format("8:30") == (True, "08:30:00")
    assert normalize_and_validate_time_format("23:59") == (True, "23:59:00")

    # Test that HH:MM:SS stays unchanged
    assert normalize_and_validate_time_format("08:30:00") == (True, "08:30:00")
    assert normalize_and_validate_time_format("23:59:59") == (True, "23:59:59")

    # Test empty/None values
    assert normalize_and_validate_time_format("") == (True, None)
    assert normalize_and_validate_time_format(None) == (True, None)

    # Test invalid formats return False with None
    assert normalize_and_validate_time_format("25:30") == (False, None)
    assert normalize_and_validate_time_format("08:60") == (False, None)
    assert normalize_and_validate_time_format("invalid") == (False, None)
    assert normalize_and_validate_time_format("08:30:60") == (False, None)
    assert normalize_and_validate_time_format("08") == (False, None)
