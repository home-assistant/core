"""Test the Qingping binary sensors."""
from datetime import timedelta
import time
from unittest.mock import patch

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.qingping.const import DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import LIGHT_AND_SIGNAL_SERVICE_INFO, NO_DATA_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
)


async def test_binary_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the binary sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("binary_sensor")) == 0
    inject_bluetooth_service_info(hass, LIGHT_AND_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("binary_sensor")) == 1

    motion_sensor = hass.states.get("binary_sensor.motion_light_eeff_motion")
    assert motion_sensor.state == "off"
    assert motion_sensor.attributes[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Motion"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_binary_sensor_restore_state(hass: HomeAssistant) -> None:
    """Test setting up creates the binary sensors and restoring state."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("binary_sensor")) == 0
    inject_bluetooth_service_info(hass, LIGHT_AND_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("binary_sensor")) == 1

    motion_sensor = hass.states.get("binary_sensor.motion_light_eeff_motion")
    assert motion_sensor.state == STATE_OFF
    assert motion_sensor.attributes[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Motion"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=monotonic_now,
    ), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Device is no longer available because its not in range

    motion_sensor = hass.states.get("binary_sensor.motion_light_eeff_motion")
    assert motion_sensor.state == STATE_UNAVAILABLE

    # Device is back in range

    inject_bluetooth_service_info(hass, NO_DATA_SERVICE_INFO)

    motion_sensor = hass.states.get("binary_sensor.motion_light_eeff_motion")
    assert motion_sensor.state == STATE_OFF
