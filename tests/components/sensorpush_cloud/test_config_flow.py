"""Test the SensorPush Cloud config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from homeassistant import config_entries
from homeassistant.components.sensorpush_cloud.api import SensorPushCloudError
from homeassistant.components.sensorpush_cloud.const import CONF_DEVICE_IDS, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_SENSORS


@pytest.mark.sensors(MOCK_SENSORS)
async def test_form(
    hass: HomeAssistant, mock_api: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure"
    assert result["errors"] == {}

    device_ids = list(MOCK_SENSORS.keys())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_IDS: device_ids},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
        CONF_DEVICE_IDS: device_ids,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_api_error(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Test we display API errors to the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_api.async_authorize.side_effect = SensorPushCloudError("test-message")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "test-message"}


async def test_form_unknown_error(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Test we display unknown errors to the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    mock_api.async_authorize.side_effect = Exception("test-message")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.sensors({})
async def test_form_no_devices_found(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """Test we display an error when no devices are found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure"
    assert result["errors"] == {"base": "no_devices_found"}


@pytest.mark.sensors(MOCK_SENSORS)
async def test_form_no_devices_selected(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Test we abort when no devices are selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "configure"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_DEVICE_IDS: [],
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_selected"
