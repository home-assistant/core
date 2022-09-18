"""Test the ibeacon device trackers."""


from datetime import timedelta

import pytest

from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.ibeacon.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_HOME, STATE_NOT_HOME
from homeassistant.util import dt as dt_util

from . import BLUECHARM_BEACON_SERVICE_INFO, BLUECHARM_BLE_DEVICE

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


async def test_device_Tracker(hass):
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

    tracker = hass.states.get("device_tracker.bluecharm_177999")
    tracker_attributes = tracker.attributes
    assert tracker.state == STATE_HOME
    assert tracker_attributes[ATTR_FRIENDLY_NAME] == "BlueCharm_177999"

    with patch_all_discovered_devices([]):
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS * 2)
        )
        await hass.async_block_till_done()

    tracker = hass.states.get("device_tracker.bluecharm_177999")
    assert tracker.state == STATE_NOT_HOME

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
