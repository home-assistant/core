"""Test the ibeacon sensors."""
from datetime import timedelta
import time

from bleak.backends.scanner import BLEDevice
import pytest

from homeassistant.components.ibeacon.const import ATTR_SOURCE, DOMAIN, UPDATE_INTERVAL
from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.util import dt as dt_util

from . import (
    BLUECHARM_BEACON_SERVICE_INFO,
    BLUECHARM_BEACON_SERVICE_INFO_2,
    BLUECHARM_BEACON_SERVICE_INFO_DBUS,
    TESLA_TRANSIENT,
    TESLA_TRANSIENT_BLE_DEVICE,
    bluetooth_service_info_replace as replace,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    generate_advertisement_data,
    inject_advertisement_with_time_and_source_connectable,
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


async def test_many_groups_same_address_ignored(hass: HomeAssistant) -> None:
    """Test the different uuid, major, minor from many addresses removes all associated entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.bluecharm_177999_8105_estimated_distance") is not None
    )

    for i in range(12):
        service_info = BluetoothServiceInfo(
            name="BlueCharm_177999",
            address="61DE521B-F0BF-9F44-64D4-75BBE1738105",
            rssi=-63,
            service_data={},
            manufacturer_data={
                76: b"\x02\x15BlueCharmBeacons" + bytearray([i]) + b"\xfe\x13U\xc5"
            },
            service_uuids=[],
            source="local",
        )
        inject_bluetooth_service_info(hass, service_info)

    await hass.async_block_till_done()
    assert hass.states.get("sensor.bluecharm_177999_8105_estimated_distance") is None


async def test_ignore_not_ibeacons(hass: HomeAssistant) -> None:
    """Test we ignore non-ibeacon data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    before_entity_count = len(hass.states.async_entity_ids())
    inject_bluetooth_service_info(
        hass,
        replace(
            BLUECHARM_BEACON_SERVICE_INFO, manufacturer_data={76: b"\x02\x15invalid"}
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == before_entity_count


async def test_ignore_no_name_but_create_if_set_later(hass: HomeAssistant) -> None:
    """Test we ignore devices with no name but create it if it set set later."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    before_entity_count = len(hass.states.async_entity_ids())
    inject_bluetooth_service_info(
        hass,
        replace(BLUECHARM_BEACON_SERVICE_INFO, name=None),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == before_entity_count

    inject_bluetooth_service_info(
        hass,
        replace(
            BLUECHARM_BEACON_SERVICE_INFO,
            service_data={
                "00002080-0000-1000-8000-00805f9b34fb": b"j\x0c\x0e\xfe\x13U",
                "0000feaa-0000-1000-8000-00805f9b34fb": (
                    b" \x00\x0c\x00\x1c\x00\x00\x00\x06h\x00\x008\x10"
                ),
            },
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) > before_entity_count


async def test_ignore_default_name(hass: HomeAssistant) -> None:
    """Test we ignore devices with default name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    before_entity_count = len(hass.states.async_entity_ids())
    inject_bluetooth_service_info(
        hass,
        replace(
            BLUECHARM_BEACON_SERVICE_INFO_DBUS,
            name=BLUECHARM_BEACON_SERVICE_INFO_DBUS.address,
        ),
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == before_entity_count


async def test_rotating_major_minor_and_mac_with_name(hass: HomeAssistant) -> None:
    """Test the different uuid, major, minor from many addresses removes all associated entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    before_entity_count = len(hass.states.async_entity_ids("device_tracker"))

    for i in range(100):
        service_info = BluetoothServiceInfo(
            name="BlueCharm_177999",
            address=f"AA:BB:CC:DD:EE:{i:02X}",
            rssi=-63,
            service_data={},
            manufacturer_data={
                76: b"\x02\x15BlueCharmBeacons"
                + bytearray([i])
                + b"\xfe"
                + bytearray([i])
                + b"U\xc5"
            },
            service_uuids=[],
            source="local",
        )
        inject_bluetooth_service_info(hass, service_info)
        await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("device_tracker")) == before_entity_count


async def test_rotating_major_minor_and_mac_no_name(hass: HomeAssistant) -> None:
    """Test no-name devices with different uuid, major, minor from many addresses removes all associated entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    before_entity_count = len(hass.states.async_entity_ids("device_tracker"))

    for i in range(51):
        service_info = BluetoothServiceInfo(
            name=f"AA:BB:CC:DD:EE:{i:02X}",
            address=f"AA:BB:CC:DD:EE:{i:02X}",
            rssi=-63,
            service_data={},
            manufacturer_data={
                76: b"\x02\x15BlueCharmBeacons"
                + bytearray([i])
                + b"\xfe"
                + bytearray([i])
                + b"U\xc5"
            },
            service_uuids=[],
            source="local",
        )
        inject_bluetooth_service_info(hass, service_info)
        await hass.async_block_till_done()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("device_tracker")) == before_entity_count


async def test_ignore_transient_devices_unless_we_see_them_a_few_times(
    hass: HomeAssistant,
) -> None:
    """Test we ignore transient devices unless we see them a few times."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    before_entity_count = len(hass.states.async_entity_ids())
    inject_bluetooth_service_info(
        hass,
        TESLA_TRANSIENT,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == before_entity_count

    with patch_all_discovered_devices([TESLA_TRANSIENT_BLE_DEVICE]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL.total_seconds() * 2),
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == before_entity_count

    for i in range(3, 17):
        with patch_all_discovered_devices([TESLA_TRANSIENT_BLE_DEVICE]):
            async_fire_time_changed(
                hass,
                dt_util.utcnow()
                + timedelta(seconds=UPDATE_INTERVAL.total_seconds() * 2 * i),
            )
            await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) > before_entity_count

    assert hass.states.get("device_tracker.s6da7c9389bd5452cc_cccc").state == STATE_HOME

    await hass.config_entries.async_reload(entry.entry_id)

    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.s6da7c9389bd5452cc_cccc").state == STATE_HOME


async def test_changing_source_attribute(hass: HomeAssistant) -> None:
    """Test update of the source attribute."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    now = time.monotonic()
    info = BLUECHARM_BEACON_SERVICE_INFO_2
    device = BLEDevice(
        address=info.address,
        name=info.name,
        details={},
    )
    advertisement_data = generate_advertisement_data(
        local_name=info.name,
        manufacturer_data=info.manufacturer_data,
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        rssi=info.rssi,
    )

    inject_advertisement_with_time_and_source_connectable(
        hass,
        device,
        advertisement_data,
        now,
        "local",
        True,
    )
    await hass.async_block_till_done()

    attributes = hass.states.get(
        "sensor.bluecharm_177999_8105_estimated_distance"
    ).attributes
    assert attributes[ATTR_SOURCE] == "local"

    inject_advertisement_with_time_and_source_connectable(
        hass,
        device,
        advertisement_data,
        now,
        "proxy",
        True,
    )
    await hass.async_block_till_done()
    with patch_all_discovered_devices([BLUECHARM_BEACON_SERVICE_INFO_2]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=UPDATE_INTERVAL.total_seconds() * 2),
        )
        await hass.async_block_till_done()

    attributes = hass.states.get(
        "sensor.bluecharm_177999_8105_estimated_distance"
    ).attributes
    assert attributes[ATTR_SOURCE] == "proxy"
