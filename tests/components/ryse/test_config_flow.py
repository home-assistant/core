"""Test RYSE BLE config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.ryse.config_flow import RyseBLEDeviceConfigFlow
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_user_step_show_form(hass: HomeAssistant) -> None:
    """Test showing the initial form."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_pairing_search_no_devices(hass: HomeAssistant) -> None:
    """Test when no RYSE devices found."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass

    with (
        patch(
            "homeassistant.components.ryse.config_flow.async_discovered_service_info",
            return_value=[],
        ),
        patch(
            "homeassistant.components.ryse.config_flow.filter_ryse_devices_pairing",
            return_value=[],
        ),
    ):
        result = await flow.async_step_pairing_search()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "pairing_search"


@pytest.mark.asyncio
async def test_pairing_search_with_devices(hass: HomeAssistant) -> None:
    """Test discovered RYSE devices."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass

    mock_devices = ["RYSE Shade (AA:BB:CC:DD:EE:FF)"]

    with (
        patch(
            "homeassistant.components.ryse.config_flow.async_discovered_service_info",
            return_value=[{"address": "AA:BB:CC:DD:EE:FF"}],
        ),
        patch(
            "homeassistant.components.ryse.config_flow.filter_ryse_devices_pairing",
            return_value=mock_devices,
        ),
        patch.object(flow, "context", {"device_options": mock_devices}),
    ):
        result = await flow.async_step_pairing_search()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "select_device"


@pytest.mark.asyncio
async def test_select_device_and_pair_success(hass: HomeAssistant) -> None:
    """Test selecting and pairing device successfully."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.device_options = ["Shade1 (AA:BB:CC:DD:EE:FF)"]

    with (
        patch(
            "homeassistant.components.ryse.config_flow.RyseBLEDeviceConfigFlow.async_set_unique_id",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.ryse.config_flow.pair_with_ble_device",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await flow.async_step_select_device(
            {"device": "Shade1 (AA:BB:CC:DD:EE:FF)"}
        )
        assert flow.selected_device["address"] == "AA:BB:CC:DD:EE:FF"

        result = await flow.async_step_pair()
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "RYSE gear Shade1"
        assert result["data"]["address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_pairing_failure(hass: HomeAssistant) -> None:
    """Test when BLE pairing fails."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.selected_device = {"name": "Shade", "address": "AA:BB"}

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        new=AsyncMock(return_value=False),
    ):
        result = await flow.async_step_pair()
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "pair"


@pytest.mark.asyncio
async def test_pairing_raises_exception(hass: HomeAssistant) -> None:
    """Test pairing raises unexpected exception."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.selected_device = {"name": "Shade", "address": "AA:BB"}

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        new=AsyncMock(side_effect=Exception("oops")),
    ):
        result = await flow.async_step_pair()
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "Unexpected error"
