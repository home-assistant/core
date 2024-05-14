"""Test Bluetooth LE device tracker."""

from datetime import timedelta
from unittest.mock import patch

from bleak import BleakError
from freezegun import freeze_time

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth_le_tracker import device_tracker
from homeassistant.components.bluetooth_le_tracker.device_tracker import (
    CONF_TRACK_BATTERY,
    CONF_TRACK_BATTERY_INTERVAL,
)
from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    DOMAIN,
    legacy,
)
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, slugify

from tests.common import async_fire_time_changed
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device


class MockBleakClient:
    """Mock BleakClient."""

    def __init__(self, *args, **kwargs):
        """Mock BleakClient."""

    async def __aenter__(self, *args, **kwargs):
        """Mock BleakClient.__aenter__."""
        return self

    async def __aexit__(self, *args, **kwargs):
        """Mock BleakClient.__aexit__."""


class MockBleakClientTimesOut(MockBleakClient):
    """Mock BleakClient that times out."""

    async def read_gatt_char(self, *args, **kwargs):
        """Mock BleakClient.read_gatt_char."""
        raise TimeoutError


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


async def test_do_not_see_device_if_time_not_updated(
    hass: HomeAssistant,
    mock_bluetooth: None,
    mock_device_tracker_conf: list[legacy.Device],
) -> None:
    """Test device going not_home after consider_home threshold from first scan if the subsequent scans have not incremented last seen time."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info:
        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=0,
            connectable=False,
            tx_power=-127,
        )
        # Return with name with time = 0 for all the updates
        mock_async_discovered_service_info.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_NEW: True,
            CONF_CONSIDER_HOME: timedelta(minutes=10),
        }
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()
        assert result

        # Tick until device seen enough times for to be registered for tracking
        for _ in range(device_tracker.MIN_SEEN_NEW):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + config[CONF_SCAN_INTERVAL] + timedelta(seconds=1),
            )
            await hass.async_block_till_done()

        # Advance time to trigger updates
        time_after_consider_home = dt_util.utcnow() + config[CONF_CONSIDER_HOME] / 2
        with freeze_time(time_after_consider_home):
            async_fire_time_changed(hass, time_after_consider_home)
            await hass.async_block_till_done()

        # Advance time over the consider home threshold and trigger update after the threshold
        time_after_consider_home = dt_util.utcnow() + config[CONF_CONSIDER_HOME]
        with freeze_time(time_after_consider_home):
            async_fire_time_changed(hass, time_after_consider_home)
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "not_home"


async def test_see_device_if_time_updated(
    hass: HomeAssistant,
    mock_bluetooth: None,
    mock_device_tracker_conf: list[legacy.Device],
) -> None:
    """Test device remaining home after consider_home threshold from first scan if the subsequent scans have incremented last seen time."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info:
        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=0,
            connectable=False,
            tx_power=-127,
        )
        # Return with name with time = 0 initially
        mock_async_discovered_service_info.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_NEW: True,
            CONF_CONSIDER_HOME: timedelta(minutes=10),
        }
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        assert result

        # Tick until device seen enough times for to be registered for tracking
        for _ in range(device_tracker.MIN_SEEN_NEW):
            async_fire_time_changed(
                hass,
                dt_util.utcnow() + config[CONF_SCAN_INTERVAL] + timedelta(seconds=1),
            )
            await hass.async_block_till_done()

        # Increment device time so it gets seen in the next update
        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=1,
            connectable=False,
            tx_power=-127,
        )
        # Return with name with time = 0 initially
        mock_async_discovered_service_info.return_value = [device]
        # Advance time to trigger updates
        time_after_consider_home = dt_util.utcnow() + config[CONF_CONSIDER_HOME] / 2
        with freeze_time(time_after_consider_home):
            async_fire_time_changed(hass, time_after_consider_home)
            await hass.async_block_till_done()

        # Advance time over the consider home threshold and trigger update after the threshold
        time_after_consider_home = dt_util.utcnow() + config[CONF_CONSIDER_HOME]
        with freeze_time(time_after_consider_home):
            async_fire_time_changed(hass, time_after_consider_home)
            await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "home"


async def test_preserve_new_tracked_device_name(
    hass: HomeAssistant,
    mock_bluetooth: None,
    mock_device_tracker_conf: list[legacy.Device],
) -> None:
    """Test preserving tracked device name across new seens."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info:
        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=0,
            connectable=False,
            tx_power=-127,
        )
        # Return with name when seen first time
        mock_async_discovered_service_info.return_value = [device]

        config = {
            CONF_PLATFORM: "bluetooth_le_tracker",
            CONF_SCAN_INTERVAL: timedelta(minutes=1),
            CONF_TRACK_NEW: True,
        }
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()

        # Seen once here; return without name when seen subsequent times
        device = BluetoothServiceInfoBleak(
            name=None,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=0,
            connectable=False,
            tx_power=-127,
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
    hass: HomeAssistant,
    mock_bluetooth: None,
    mock_device_tracker_conf: list[legacy.Device],
) -> None:
    """Test tracking the battery times out."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info:
        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=0,
            connectable=False,
            tx_power=-127,
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
        await hass.async_block_till_done()
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


async def test_tracking_battery_fails(
    hass: HomeAssistant,
    mock_bluetooth: None,
    mock_device_tracker_conf: list[legacy.Device],
) -> None:
    """Test tracking the battery fails."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info:
        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=0,
            connectable=False,
            tx_power=-127,
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
    hass: HomeAssistant,
    mock_bluetooth: None,
    mock_device_tracker_conf: list[legacy.Device],
) -> None:
    """Test tracking the battery gets a value."""

    address = "DE:AD:BE:EF:13:37"
    name = "Mock device name"
    entity_id = f"{DOMAIN}.{slugify(name)}"

    with patch(
        "homeassistant.components.bluetooth.async_discovered_service_info"
    ) as mock_async_discovered_service_info:
        device = BluetoothServiceInfoBleak(
            name=name,
            address=address,
            rssi=-19,
            manufacturer_data={},
            service_data={},
            service_uuids=[],
            source="local",
            device=generate_ble_device(address, None),
            advertisement=generate_advertisement_data(local_name="empty"),
            time=0,
            connectable=True,
            tx_power=-127,
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
        await hass.async_block_till_done()
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
