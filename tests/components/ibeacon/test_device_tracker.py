"""Test the ibeacon device trackers."""

from datetime import timedelta
import time
from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_last_service_info,
)
from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.ibeacon.const import (
    DOMAIN,
    UNAVAILABLE_TIMEOUT,
    UPDATE_INTERVAL,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import (
    BEACON_RANDOM_ADDRESS_SERVICE_INFO,
    BLUECHARM_BEACON_SERVICE_INFO,
    BLUECHARM_BLE_DEVICE,
    bluetooth_service_info_replace as replace,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    inject_bluetooth_service_info_bleak,
    patch_all_discovered_devices,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


async def test_device_tracker_fixed_address(hass: HomeAssistant) -> None:
    """Test creating and updating device_tracker."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch_all_discovered_devices([BLUECHARM_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
        await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.bluecharm_177999_8105")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "BlueCharm_177999 8105"

    with patch_all_discovered_devices([]):
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS * 2)
        )
        await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.bluecharm_177999_8105")
    assert tracker.state == STATE_NOT_HOME

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_device_tracker_random_address(hass: HomeAssistant) -> None:
    """Test creating and updating device_tracker."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)
    start_time = time.monotonic()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for i in range(20):
        inject_bluetooth_service_info(
            hass,
            replace(
                BEACON_RANDOM_ADDRESS_SERVICE_INFO, address=f"AA:BB:CC:DD:EE:{i:02X}"
            ),
        )
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "RandomAddress_1234"

    await hass.async_block_till_done()
    with (
        patch_all_discovered_devices([]),
        patch(
            "homeassistant.components.ibeacon.coordinator.MONOTONIC_TIME",
            return_value=start_time + UNAVAILABLE_TIMEOUT + 1,
        ),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TIMEOUT)
        )
        await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    assert tracker.state == STATE_NOT_HOME

    inject_bluetooth_service_info(
        hass, replace(BEACON_RANDOM_ADDRESS_SERVICE_INFO, address="AA:BB:CC:DD:EE:DD")
    )
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "RandomAddress_1234"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "RandomAddress_1234"


async def test_device_tracker_random_address_infrequent_changes(
    hass: HomeAssistant,
) -> None:
    """Test creating and updating device_tracker with a random mac that only changes once per day."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)
    start_time = time.monotonic()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for i in range(20):
        inject_bluetooth_service_info(
            hass,
            replace(
                BEACON_RANDOM_ADDRESS_SERVICE_INFO, address=f"AA:BB:CC:DD:EE:{i:02X}"
            ),
        )
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "RandomAddress_1234"

    await hass.async_block_till_done()
    with (
        patch_all_discovered_devices([]),
        patch(
            "homeassistant.components.ibeacon.coordinator.MONOTONIC_TIME",
            return_value=start_time + UNAVAILABLE_TIMEOUT + 1,
        ),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TIMEOUT)
        )
        await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    assert tracker.state == STATE_NOT_HOME

    inject_bluetooth_service_info(
        hass, replace(BEACON_RANDOM_ADDRESS_SERVICE_INFO, address="AA:BB:CC:DD:EE:14")
    )
    await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "RandomAddress_1234"

    inject_bluetooth_service_info(
        hass, replace(BEACON_RANDOM_ADDRESS_SERVICE_INFO, address="AA:BB:CC:DD:EE:14")
    )
    device = async_ble_device_from_address(hass, "AA:BB:CC:DD:EE:14", False)

    with (
        patch_all_discovered_devices([device]),
        patch(
            "homeassistant.components.ibeacon.coordinator.MONOTONIC_TIME",
            return_value=start_time + UPDATE_INTERVAL.total_seconds() + 1,
        ),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "RandomAddress_1234"

    one_day_future = start_time + 86400
    previous_service_info = async_last_service_info(
        hass, "AA:BB:CC:DD:EE:14", connectable=False
    )
    inject_bluetooth_service_info_bleak(
        hass,
        BluetoothServiceInfoBleak(
            name="RandomAddress_1234",
            address="AA:BB:CC:DD:EE:14",
            rssi=-63,
            service_data={},
            manufacturer_data={76: b"\x02\x15RandCharmBeacons\x0e\xfe\x13U\xc5"},
            service_uuids=[],
            source="local",
            time=one_day_future,
            connectable=False,
            device=device,
            advertisement=previous_service_info.advertisement,
            tx_power=-127,
        ),
    )
    device = async_ble_device_from_address(hass, "AA:BB:CC:DD:EE:14", False)
    assert (
        async_last_service_info(hass, "AA:BB:CC:DD:EE:14", connectable=False).time
        == one_day_future
    )

    with (
        patch_all_discovered_devices([device]),
        patch(
            "homeassistant.components.ibeacon.coordinator.MONOTONIC_TIME",
            return_value=start_time + UNAVAILABLE_TIMEOUT + 1,
        ),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TIMEOUT + 1)
        )
        await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.randomaddress_1234")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "RandomAddress_1234"
