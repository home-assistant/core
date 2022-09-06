"""Test Bluetooth LE device tracker."""

import asyncio
from datetime import timedelta
from unittest.mock import patch

from bleak import BleakError
from bleak.backends.scanner import AdvertisementData, BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth_le_tracker import device_tracker
from homeassistant.components.bluetooth_le_tracker.device_tracker import (
    CONF_TRACK_BATTERY,
    CONF_TRACK_BATTERY_INTERVAL,
)
from homeassistant.components.device_tracker.const import (
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    DOMAIN,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify

from tests.common import async_fire_time_changed


class MockBleakClient:
    """Mock BleakClient."""

    def __init__(self, *args, **kwargs):
        """Mock BleakClient."""
        pass

    async def __aenter__(self, *args, **kwargs):
        """Mock BleakClient.__aenter__."""
        return self

    async def __aexit__(self, *args, **kwargs):
        """Mock BleakClient.__aexit__."""
        pass


class MockBleakClientTimesOut(MockBleakClient):
    """Mock BleakClient that times out."""

    async def read_gatt_char(self, *args, **kwargs):
        """Mock BleakClient.read_gatt_char."""
        raise asyncio.TimeoutError


class MockBleakClientFailing(MockBleakClient):
    """Mock BleakClient that fails."""

    async def read_gatt_char(self, *args, **kwargs):
        """Mock BleakClient.read_gatt_char."""
        raise BleakError("Failed")


class MockBleakClientBattery5(MockBleakClient):
    """Mock BleakClient that returns a battery level of 5."""

    async def read_gatt_char(self, *args, **kwargs):
        """Mock BleakClient.read_gatt_char."""
        return b"\x05"


async def test_preserve_new_tracked_device_name(
    hass, mock_bluetooth, mock_device_tracker_conf
):
    """Test preserving tracked device name across new seens."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info, patch.object(
        device_tracker, "MIN_SEEN_NEW", 3
    ):

        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=BLEDevice(address, None),
            advertisement=AdvertisementData(local_name="empty"),
            time=0,
            connectable=False,
        )
        # Return with name when seen first time
        mock_async_discovered_service_info.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_NEW: True,
        }
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        assert result

        # Seen once here; return without name when seen subsequent times
        device = BluetoothServiceInfoBleak(
            name=None,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=BLEDevice(address, None),
            advertisement=AdvertisementData(local_name="empty"),
            time=0,
            connectable=False,
        )
        # Return with name when seen first time
        mock_async_discovered_service_info.return_value = [device]

        # Tick until device seen enough times for to be registered for tracking
        for _ in range(device_tracker.MIN_SEEN_NEW - 1):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + config[CONF_SCAN_INTERVAL] + timedelta(seconds=1),
            )
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.name == name


async def test_tracking_battery_times_out(
    hass, mock_bluetooth, mock_device_tracker_conf
):
    """Test tracking the battery times out."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info, patch.object(
        device_tracker, "MIN_SEEN_NEW", 3
    ):

        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=BLEDevice(address, None),
            advertisement=AdvertisementData(local_name="empty"),
            time=0,
            connectable=False,
        )
        # Return with name when seen first time
        mock_async_discovered_service_info.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_BATTERY: True,
            CONF_TRACK_BATTERY_INTERVAL: timedelta(minutes=2),
            CONF_TRACK_NEW: True,
        }
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        assert result

        # Tick until device seen enough times for to be registered for tracking
        for _ in range(device_tracker.MIN_SEEN_NEW - 1):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + config[CONF_SCAN_INTERVAL] + timedelta(seconds=1),
            )
            await hass.async_block_till_done()

        with patch(
            "homeassistant.components.bluetooth_le_tracker.device_tracker.BleakClient",
            MockBleakClientTimesOut,
        ):
            # Wait for the battery scan
            async_fire_time_changed(
                hass,
                dt_util.utcnow()
                + config[CONF_SCAN_INTERVAL]
                + timedelta(seconds=1)
                + timedelta(minutes=2),
            )
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.name == name
    assert "battery" not in state.attributes


async def test_tracking_battery_fails(hass, mock_bluetooth, mock_device_tracker_conf):
    """Test tracking the battery fails."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info, patch.object(
        device_tracker, "MIN_SEEN_NEW", 3
    ):

        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=BLEDevice(address, None),
            advertisement=AdvertisementData(local_name="empty"),
            time=0,
            connectable=False,
        )
        # Return with name when seen first time
        mock_async_discovered_service_info.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_BATTERY: True,
            CONF_TRACK_BATTERY_INTERVAL: timedelta(minutes=2),
            CONF_TRACK_NEW: True,
        }
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        assert result

        # Tick until device seen enough times for to be registered for tracking
        for _ in range(device_tracker.MIN_SEEN_NEW - 1):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + config[CONF_SCAN_INTERVAL] + timedelta(seconds=1),
            )
            await hass.async_block_till_done()

        with patch(
            "homeassistant.components.bluetooth_le_tracker.device_tracker.BleakClient",
            MockBleakClientFailing,
        ):
            # Wait for the battery scan
            async_fire_time_changed(
                hass,
                dt_util.utcnow()
                + config[CONF_SCAN_INTERVAL]
                + timedelta(seconds=1)
                + timedelta(minutes=2),
            )
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.name == name
    assert "battery" not in state.attributes


async def test_tracking_battery_successful(
    hass, mock_bluetooth, mock_device_tracker_conf
):
    """Test tracking the battery gets a value."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info, patch.object(
        device_tracker, "MIN_SEEN_NEW", 3
    ):

        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=BLEDevice(address, None),
            advertisement=AdvertisementData(local_name="empty"),
            time=0,
            connectable=True,
        )
        # Return with name when seen first time
        mock_async_discovered_service_info.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_BATTERY: True,
            CONF_TRACK_BATTERY_INTERVAL: timedelta(minutes=2),
            CONF_TRACK_NEW: True,
        }
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        assert result

        # Tick until device seen enough times for to be registered for tracking
        for _ in range(device_tracker.MIN_SEEN_NEW - 1):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + config[CONF_SCAN_INTERVAL] + timedelta(seconds=1),
            )
            await hass.async_block_till_done()

        with patch(
            "homeassistant.components.bluetooth_le_tracker.device_tracker.BleakClient",
            MockBleakClientBattery5,
        ):
            # Wait for the battery scan
            async_fire_time_changed(
                hass,
                dt_util.utcnow()
                + config[CONF_SCAN_INTERVAL]
                + timedelta(seconds=1)
                + timedelta(minutes=2),
            )
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.name == name
    assert state.attributes["battery"] == 5
