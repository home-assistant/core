"""Test the ibeacon sensors."""


from datetime import timedelta

import pytest

from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.ibeacon.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.util import dt as dt_util

from . import (
    BLUECHARM_BEACON_SERVICE_INFO,
    BLUECHARM_BEACON_SERVICE_INFO_2,
    BLUECHARM_BLE_DEVICE,
)

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
)


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth):
    """Auto mock bluetooth."""


async def test_sensors(hass):
    """Test creating and updating sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch_all_discovered_devices([BLUECHARM_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO)
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.bluecharm_177999_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "1.6"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME] == "BlueCharm_177999 Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    with patch_all_discovered_devices([BLUECHARM_BLE_DEVICE]):
        inject_bluetooth_service_info(hass, BLUECHARM_BEACON_SERVICE_INFO_2)
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.bluecharm_177999_estimated_distance")
    distance_attributes = distance_sensor.attributes
    assert distance_sensor.state == "0.3"
    assert (
        distance_attributes[ATTR_FRIENDLY_NAME] == "BlueCharm_177999 Estimated Distance"
    )
    assert distance_attributes[ATTR_UNIT_OF_MEASUREMENT] == "m"
    assert distance_attributes[ATTR_STATE_CLASS] == "measurement"

    with patch_all_discovered_devices([]):
        await hass.async_block_till_done()
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS * 2)
        )
        await hass.async_block_till_done()

    distance_sensor = hass.states.get("sensor.bluecharm_177999_estimated_distance")
    assert distance_sensor.state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
