"""Tests for Xthings Cloud config flow."""

from unittest.mock import AsyncMock

from ha_xthings_cloud import XthingsCloudApiError, XthingsCloudAuthError
import pytest

from homeassistant.components.xthings_cloud.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
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


async def test_reauth_updates_existing_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Reauthentication handles login errors, updates tokens, and keeps options."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"native_mqtt": True}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    mock_api_client.async_login.side_effect = XthingsCloudAuthError(
        "Wrong password", code=21014
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["errors"] == {"base": "password_wrong"}
    mock_api_client.async_login.side_effect = None
    mock_api_client.async_login.return_value.update(
        token="new_token", refresh_token="new_refresh_token"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: MOCK_EMAIL, CONF_PASSWORD: MOCK_PASSWORD},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_EMAIL: MOCK_EMAIL,
        CONF_TOKEN: "new_token",
        CONF_REFRESH_TOKEN: "new_refresh_token",
    }
    assert mock_config_entry.options == {"native_mqtt": True}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_rejects_different_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Reauthentication must not replace an entry with another account."""
    mock_config_entry.add_to_hass(hass)
    original_data = dict(mock_config_entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    mock_api_client.async_login.return_value["user_id"] = "another_user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "another@example.com", CONF_PASSWORD: MOCK_PASSWORD},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data == original_data


async def test_native_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Native MQTT can be enabled without supplying certificate paths."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert set(result["data_schema"].schema) == {"native_mqtt"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"native_mqtt": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {"native_mqtt": True}


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
