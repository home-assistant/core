"""Test RYSE BLE config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.ryse.config_flow import RyseBLEDeviceConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant


def _make_info():
    return BluetoothServiceInfoBleak(
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


# ---------------------------------------------------------------------------
# BLUETOOTH FLOW TESTS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bluetooth_flow_show_confirm_form(hass: HomeAssistant) -> None:
    """Test showing confirmation form when a BLE device is discovered."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = _make_info()

    result = await flow.async_step_bluetooth(discovery_info)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert flow._discovery_info == discovery_info


@pytest.mark.asyncio
async def test_bluetooth_confirm_success(hass: HomeAssistant) -> None:
    """Test successful pairing from bluetooth auto-discovery."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = _make_info()
    flow._discovery_info = discovery_info

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        AsyncMock(return_value=True),
    ):
        result = await flow.async_step_bluetooth_confirm(user_input={})

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "RYSE Shade"
    assert result["data"] == {}


@pytest.mark.asyncio
async def test_bluetooth_confirm_failure(hass: HomeAssistant) -> None:
    """Test pairing fails from bluetooth auto-discovery."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = _make_info()
    flow._discovery_info = discovery_info

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        AsyncMock(return_value=False),
    ):
        result = await flow.async_step_bluetooth_confirm(user_input={})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_bluetooth_confirm_exception(hass: HomeAssistant) -> None:
    """Test unexpected exception during bluetooth pairing."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    discovery_info = _make_info()
    flow._discovery_info = discovery_info

    with patch(
        "homeassistant.components.ryse.config_flow.pair_with_ble_device",
        AsyncMock(side_effect=Exception("oops")),
    ):
        result = await flow.async_step_bluetooth_confirm(user_input={})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    assert result["errors"]["base"] == "unknown"


# ---------------------------------------------------------------------------
# USER-INITIATED FLOW TESTS
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test manual add — no devices in pairing mode."""
    flow = RyseBLEDeviceConfigFlow()
    flow.hass = hass
    flow.context = {}

    with patch(
        "homeassistant.components.ryse.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


@pytest.mark.asyncio
async def test_user_show_selection_form(hass: HomeAssistant) -> None:
    """Test manual add — pairing device found → show dropdown list."""
    info = _make_info()

    with (
        patch(
            "homeassistant.components.ryse.config_flow.async_discovered_service_info",
            return_value=[info],
        ),
        patch(
            "homeassistant.components.ryse.config_flow.is_pairing_ryse_device",
            AsyncMock(return_value=True),
        ),
    ):
        flow = RyseBLEDeviceConfigFlow()
        flow.hass = hass
        flow.context = {}

        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_ADDRESS in result["data_schema"].schema


@pytest.mark.asyncio
async def test_user_pair_success(hass: HomeAssistant) -> None:
    """Test manual add → successful pairing."""
    info = _make_info()

    with (
        patch(
            "homeassistant.components.ryse.config_flow.async_discovered_service_info",
            return_value=[info],
        ),
        patch(
            "homeassistant.components.ryse.config_flow.is_pairing_ryse_device",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.ryse.config_flow.pair_with_ble_device",
            AsyncMock(return_value=True),
        ),
    ):
        flow = RyseBLEDeviceConfigFlow()
        flow.hass = hass
        flow.context = {}

        await flow.async_step_user()
        result = await flow.async_step_user(user_input={CONF_ADDRESS: info.address})

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "RYSE Shade"


@pytest.mark.asyncio
async def test_user_pair_fail(hass: HomeAssistant) -> None:
    """Test manual add → pairing failed."""
    info = _make_info()

    with (
        patch(
            "homeassistant.components.ryse.config_flow.async_discovered_service_info",
            return_value=[info],
        ),
        patch(
            "homeassistant.components.ryse.config_flow.is_pairing_ryse_device",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.ryse.config_flow.pair_with_ble_device",
            AsyncMock(return_value=False),
        ),
    ):
        flow = RyseBLEDeviceConfigFlow()
        flow.hass = hass
        flow.context = {}

        await flow.async_step_user()
        result = await flow.async_step_user(user_input={CONF_ADDRESS: info.address})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_user_pair_exception(hass: HomeAssistant) -> None:
    """Test manual add → unexpected exception."""
    info = _make_info()

    with (
        patch(
            "homeassistant.components.ryse.config_flow.async_discovered_service_info",
            return_value=[info],
        ),
        patch(
            "homeassistant.components.ryse.config_flow.is_pairing_ryse_device",
            AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.ryse.config_flow.pair_with_ble_device",
            AsyncMock(side_effect=Exception("boom")),
        ),
    ):
        flow = RyseBLEDeviceConfigFlow()
        flow.hass = hass
        flow.context = {}

        await flow.async_step_user()
        result = await flow.async_step_user(user_input={CONF_ADDRESS: info.address})

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
