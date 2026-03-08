"""Tests for the Kaiterra config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.kaiterra.api_data import (
    KaiterraApiAuthError,
    KaiterraApiError,
)
from homeassistant.components.kaiterra.const import AQI_SCALE, CONF_AQI_STANDARD, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration


async def test_user_flow_success(hass, mock_kaiterra_device_data) -> None:
    """Test a successful user flow."""
    with patch(
        "homeassistant.components.kaiterra.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "test-api-key",
                CONF_DEVICE_ID: "device-123",
                CONF_NAME: "Office",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Office"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_DEVICE_ID: "device-123",
        CONF_NAME: "Office",
    }
    assert mock_setup_entry.call_count == 1


async def test_user_flow_duplicate_device(hass, mock_config_entry) -> None:
    """Test duplicate device configuration aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "test-api-key",
            CONF_DEVICE_ID: "device-123",
            CONF_NAME: "Office",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_auth(hass, mock_kaiterra_auth_error) -> None:
    """Test the user flow on invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "bad-key",
            CONF_DEVICE_ID: "device-123",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_missing_device(hass, mock_kaiterra_device_not_found) -> None:
    """Test the user flow when the device does not exist."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "test-api-key",
            CONF_DEVICE_ID: "missing-device",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_not_found"}


async def test_user_flow_connection_error(hass, mock_kaiterra_api_error) -> None:
    """Test the user flow when the API cannot be reached."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_KEY: "test-api-key",
            CONF_DEVICE_ID: "device-123",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass) -> None:
    """Test the user flow on an unexpected validation error."""
    with patch(
        "homeassistant.components.kaiterra.config_flow.validate_input",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_API_KEY: "test-api-key",
                CONF_DEVICE_ID: "device-123",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_options_flow(hass, mock_config_entry) -> None:
    """Test updating the AQI standard via the options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AQI_STANDARD: "cn"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_AQI_STANDARD: "cn"}


async def test_options_flow_updates_options_and_reloads(
    hass, mock_config_entry, mock_kaiterra_device_data
) -> None:
    """Test the options flow updates the entry and reloads the integration."""
    await setup_integration(hass, mock_config_entry)

    original_coordinator = mock_config_entry.runtime_data

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not mock_config_entry.update_listeners
    assert original_coordinator.api._scale == AQI_SCALE["us"]

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_AQI_STANDARD: "cn"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_AQI_STANDARD: "cn"}
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.options == {CONF_AQI_STANDARD: "cn"}
    assert mock_config_entry.runtime_data is not original_coordinator
    assert mock_config_entry.runtime_data.api._scale == AQI_SCALE["cn"]


async def test_reauth_flow(hass, mock_config_entry, mock_kaiterra_device_data) -> None:
    """Test reauthentication updates the API key."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
        data=mock_config_entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.kaiterra.async_setup_entry",
        new=AsyncMock(return_value=True),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "new-api-key"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_API_KEY] == "new-api-key"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (KaiterraApiAuthError, "invalid_auth"),
        (KaiterraApiError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass,
    mock_config_entry,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test reauthentication flow error handling."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.kaiterra.config_flow.validate_input",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": mock_config_entry.entry_id},
            data=mock_config_entry.data,
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "new-api-key"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
