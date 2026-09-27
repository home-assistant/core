"""Tests for Xthings Cloud config flow."""

from unittest.mock import AsyncMock

from ha_xthings_cloud import XthingsCloudApiError, XthingsCloudAuthError
import pytest

from homeassistant.components.xthings_cloud.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    MOCK_EMAIL,
    MOCK_PASSWORD,
    MOCK_REFRESH_TOKEN,
    MOCK_TOKEN,
    MOCK_USER_ID,
)

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
) -> None:
    """Test successful user login flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_EMAIL
    assert result["result"].unique_id == MOCK_USER_ID
    assert result["data"] == {
        CONF_EMAIL: MOCK_EMAIL,
        CONF_TOKEN: MOCK_TOKEN,
        CONF_REFRESH_TOKEN: MOCK_REFRESH_TOKEN,
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (XthingsCloudAuthError("Auth failed", code=21014), "password_wrong"),
        (XthingsCloudApiError("API error", code=22001), "device_not_found"),
        (XthingsCloudApiError("Connection failed", code=0), "cannot_connect"),
        (RuntimeError("unexpected"), "unknown"),
    ],
)
async def test_user_flow_error_and_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user flow shows error then recovers on retry."""
    mock_api_client.async_login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error

    # Recover: repatch to succeed
    mock_api_client.async_login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_api_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts if same account already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
