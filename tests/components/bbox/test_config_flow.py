"""Tests for Bbox config flow."""

from unittest.mock import AsyncMock

from aiobbox import BboxApiError, BboxAuthError
import pytest

from homeassistant.components.bbox.const import CONF_BASE_URL, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_BASE_URL, TEST_MODEL_NAME, TEST_PASSWORD, TEST_SERIAL_NUMBER

from tests.common import MockConfigEntry


async def test_user(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test starting a flow by user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_URL: TEST_BASE_URL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_BASE_URL: TEST_BASE_URL,
        CONF_PASSWORD: TEST_PASSWORD,
    }
    assert result["result"].unique_id == TEST_SERIAL_NUMBER

    assert mock_setup_entry.called


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (BboxAuthError("Invalid credentials"), "invalid_auth"),
        (BboxApiError("Cannot connect"), "cannot_connect"),
        (TimeoutError, "timeout_connect"),
        (Exception, "unknown"),
    ],
)
async def test_exception_connection(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test starting a flow by user with a connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    mock_bbox_api.authenticate.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_URL: TEST_BASE_URL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_bbox_api.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_URL: TEST_BASE_URL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Bbox {TEST_MODEL_NAME}"
    assert result["data"] == {
        CONF_BASE_URL: TEST_BASE_URL,
        CONF_PASSWORD: TEST_PASSWORD,
    }


async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test starting a flow by user with a duplicate entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_URL: TEST_BASE_URL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_base_url(
    hass: HomeAssistant,
    mock_bbox_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test invalid base URL format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BASE_URL: "invalid-url",
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_base_url"}
