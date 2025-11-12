"""Test RYSE BLE config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.ryse.config_flow import RyseBLEDeviceConfigFlow
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_bluetooth_flow_show_confirm_form(hass: HomeAssistant) -> None:
    """Test showing the confirmation form when a BLE device is discovered."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    # Mock a Bluetooth discovery
    discovery_info = BluetoothServiceInfoBleak(
        name="RYSE Shade",
        address="AA:BB:CC:DD:EE:FF",
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        rssi=-70,
        source="local",
        tx_power=None,
        device=None,
        advertisement=None,
        connectable=True,
        time=0,
    )

    result = await flow.async_step_bluetooth(discovery_info)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert flow._discovery_info == discovery_info


@pytest.mark.asyncio
async def test_bluetooth_confirm_success(hass: HomeAssistant) -> None:
    """Test successfully confirming and pairing the BLE device."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = BluetoothServiceInfoBleak(
        name="RYSE Shade",
        address="AA:BB:CC:DD:EE:FF",
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        rssi=-70,
        source="local",
        tx_power=None,
        device=None,
        advertisement=None,
        connectable=True,
        time=0,
    )
    flow._discovery_info = discovery_info

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        new=AsyncMock(return_value=True),
    ):
        result = await flow.async_step_bluetooth_confirm(user_input={})

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "RYSE Shade"
    assert result["data"] == {}


@pytest.mark.asyncio
async def test_bluetooth_confirm_cannot_connect(hass: HomeAssistant) -> None:
    """Test pairing failure (cannot connect)."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = BluetoothServiceInfoBleak(
        name="RYSE Shade",
        address="AA:BB:CC:DD:EE:FF",
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        rssi=-70,
        source="local",
        tx_power=None,
        device=None,
        advertisement=None,
        connectable=True,
        time=0,
    )
    flow._discovery_info = discovery_info

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        new=AsyncMock(return_value=False),
    ):
        result = await flow.async_step_bluetooth_confirm(user_input={})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert "cannot_connect" in result["errors"]["base"]


@pytest.mark.asyncio
async def test_bluetooth_confirm_exception(hass: HomeAssistant) -> None:
    """Test unexpected exception during pairing."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = BluetoothServiceInfoBleak(
        name="RYSE Shade",
        address="AA:BB:CC:DD:EE:FF",
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        rssi=-70,
        source="local",
        tx_power=None,
        device=None,
        advertisement=None,
        connectable=True,
        time=0,
    )
    flow._discovery_info = discovery_info

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        new=AsyncMock(side_effect=Exception("oops")),
    ):
        result = await flow.async_step_bluetooth_confirm(user_input={})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"]["base"] == "unknown"
