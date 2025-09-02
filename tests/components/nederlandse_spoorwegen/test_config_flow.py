"""Test config flow for Nederlandse Spoorwegen integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.nederlandse_spoorwegen.api import (
    NSAPIAuthError,
    NSAPIConnectionError,
    NSAPIError,
)
from homeassistant.components.nederlandse_spoorwegen.config_flow import validate_api_key
from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.components.nederlandse_spoorwegen.utils import (
    normalize_and_validate_time_format,
    validate_time_format,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

API_KEY = "abc1234567"


async def test_config_flow_user_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper = mock_wrapper_cls.return_value
        mock_wrapper.validate_api_key = AsyncMock(return_value=True)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )

        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("title") == "Nederlandse Spoorwegen"
        assert result.get("data") == {CONF_API_KEY: API_KEY}


async def test_config_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test config flow with invalid authentication."""
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
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": "invalid_auth"}


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
        assert result.get("errors") == {"base": "invalid_auth"}


def test_validate_time_format() -> None:
    """Test the time validation function."""
    # Test valid times
    assert validate_time_format("08:30") is True
    assert validate_time_format("23:59") is True
    assert validate_time_format("00:00") is True
    assert validate_time_format("12:30:45") is True

    # Test invalid times
    assert validate_time_format("25:30") is False
    assert validate_time_format("08:60") is False
    assert validate_time_format("invalid") is False

    # Test None and empty cases (these are valid in current implementation)
    assert validate_time_format("") is True  # Empty string is valid
    assert validate_time_format(None) is True  # None is valid


def test_normalize_and_validate_time_format() -> None:
    """Test the time normalization and validation function."""
    # Test normalization from HH:MM to HH:MM:SS
    is_valid, normalized = normalize_and_validate_time_format("08:30")
    assert is_valid is True
    assert normalized == "08:30:00"

    is_valid, normalized = normalize_and_validate_time_format("23:59")
    assert is_valid is True
    assert normalized == "23:59:00"

    # Test already normalized time
    is_valid, normalized = normalize_and_validate_time_format("08:30:00")
    assert is_valid is True
    assert normalized == "08:30:00"

    is_valid, normalized = normalize_and_validate_time_format("23:59:59")
    assert is_valid is True
    assert normalized == "23:59:59"

    # Test None/empty cases
    is_valid, normalized = normalize_and_validate_time_format(None)
    assert is_valid is True
    assert normalized is None

    is_valid, normalized = normalize_and_validate_time_format("")
    assert is_valid is True
    assert normalized is None

    # Test invalid formats (should return None or raise error)
    is_valid, normalized = normalize_and_validate_time_format("invalid")
    assert is_valid is False
    assert normalized is None

    is_valid, normalized = normalize_and_validate_time_format("25:30")
    assert is_valid is False
    assert normalized is None

    is_valid, normalized = normalize_and_validate_time_format("08:60")
    assert is_valid is False
    assert normalized is None


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test successful import flow from YAML configuration."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.validate_api_key",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={CONF_API_KEY: "test_api_key"},
        )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Nederlandse Spoorwegen"
    assert result.get("data") == {CONF_API_KEY: "test_api_key"}


async def test_import_flow_already_configured(hass: HomeAssistant) -> None:
    """Test import flow when integration is already configured."""
    # First, create an existing entry
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.validate_api_key",
        return_value=True,
    ):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_API_KEY: "existing_api_key"},
        )

    # Now try to import
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.validate_api_key",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={CONF_API_KEY: "test_api_key"},
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_import_flow_no_api_key(hass: HomeAssistant) -> None:
    """Test import flow when no API key is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data={},
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "no_api_key"


async def test_import_flow_invalid_api_key(hass: HomeAssistant) -> None:
    """Test import flow with invalid API key."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.validate_api_key",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={CONF_API_KEY: "invalid_api_key"},
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "invalid_api_key"


async def test_config_flow_user_unexpected_error(hass: HomeAssistant) -> None:
    """Test config flow with unexpected NSAPIError."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper_cls.return_value.validate_api_key = AsyncMock(
            side_effect=NSAPIError("Unexpected error")
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": "invalid_auth"}


async def test_validate_api_key_ns_api_error(hass: HomeAssistant) -> None:
    """Test validate_api_key function with NSAPIError exception."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper_cls.return_value.validate_api_key = AsyncMock(
            side_effect=NSAPIError("Unexpected error")
        )

        result = await validate_api_key(hass, "test_api_key")
        assert result is False


async def test_validate_api_key_ns_api_connection_error(hass: HomeAssistant) -> None:
    """Test validate_api_key function with NSAPIConnectionError exception."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper_cls.return_value.validate_api_key = AsyncMock(
            side_effect=NSAPIConnectionError("Cannot connect")
        )

        result = await validate_api_key(hass, "test_api_key")
        assert result is False


async def test_validate_api_key_ns_api_auth_error(hass: HomeAssistant) -> None:
    """Test validate_api_key function with NSAPIAuthError exception."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
    ) as mock_wrapper_cls:
        mock_wrapper_cls.return_value.validate_api_key = AsyncMock(
            side_effect=NSAPIAuthError("Invalid API key")
        )

        result = await validate_api_key(hass, "test_api_key")
        assert result is False
