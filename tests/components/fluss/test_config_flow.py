"""Tests for the Fluss+ config flow."""

from unittest.mock import AsyncMock, patch

from fluss_api import (
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
)
import pytest

from homeassistant.components.fluss.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_successful_flow(hass: HomeAssistant, mock_api_client: AsyncMock) -> None:
    """Test successful config flow."""
    user_input = {CONF_API_KEY: "valid_api_key"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Fluss+ Devices"
    assert result["data"] == user_input


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (FlussApiClientAuthenticationError, "invalid_auth"),
        (FlussApiClientCommunicationError, "cannot_connect"),
        (ValueError, "unknown"),
    ],
)
async def test_step_user_errors(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
    mock_api_client: AsyncMock,
) -> None:
    """Test error cases for user step with recovery."""
    user_input = {CONF_API_KEY: "some_api_key"}

    class_mock = mock_api_client._mock_parent
    class_mock.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    class_mock.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Fluss+ Devices"
    assert result["data"] == user_input


async def test_unexpected_exception_logging(
    hass: HomeAssistant, mock_api_client: AsyncMock
) -> None:
    """Test logging of unexpected exceptions."""
    user_input = {CONF_API_KEY: "some_api_key"}

    with patch(
        "homeassistant.components.fluss.config_flow.LOGGER.exception"
    ) as mock_logger:
        class_mock = mock_api_client._mock_parent
        class_mock.side_effect = Exception("Unexpected error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=user_input
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}
        mock_logger.assert_called_once_with("Unexpected exception occurred")
