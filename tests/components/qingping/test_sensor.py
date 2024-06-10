"""Test the Qingping sensors."""

from datetime import timedelta
import time

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.qingping.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import LIGHT_AND_SIGNAL_SERVICE_INFO, NO_DATA_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, LIGHT_AND_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 1

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    lux_sensor_attrs = lux_sensor.attributes
    assert lux_sensor.state == "13"
    assert lux_sensor_attrs[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Illuminance"
    assert lux_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert lux_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

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

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, LIGHT_AND_SIGNAL_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 1

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    lux_sensor_attrs = lux_sensor.attributes
    assert lux_sensor.state == "13"
    assert lux_sensor_attrs[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Illuminance"
    assert lux_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert lux_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with (
        patch_bluetooth_time(
            monotonic_now,
        ),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Device is no longer available because its not in range

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    assert lux_sensor.state == STATE_UNAVAILABLE

    # Device is back in range

    inject_bluetooth_service_info(hass, NO_DATA_SERVICE_INFO)

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    assert lux_sensor.state == "13"
