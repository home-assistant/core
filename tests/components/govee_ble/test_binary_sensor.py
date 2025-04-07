"""Test the Govee BLE binary_sensor."""

from homeassistant.components.govee_ble.const import CONF_DEVICE_TYPE, DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from . import (
    GV5123_CLOSED_SERVICE_INFO,
    GV5123_OPEN_SERVICE_INFO,
    GVH5127_ABSENT_SERVICE_INFO,
    GVH5127_MOTION_SERVICE_INFO,
    GVH5127_PRESENT_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_window_sensor(hass: HomeAssistant) -> None:
    """Test setting up creates the window sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GV5123_OPEN_SERVICE_INFO.address,
        data={CONF_DEVICE_TYPE: "H5123"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, GV5123_OPEN_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    motion_sensor = hass.states.get("binary_sensor.51230f45_window")
    assert motion_sensor.state == STATE_ON

    inject_bluetooth_service_info(hass, GV5123_CLOSED_SERVICE_INFO)
    await hass.async_block_till_done()

    motion_sensor = hass.states.get("binary_sensor.51230f45_window")
    assert motion_sensor.state == STATE_OFF
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_presence_sensor(hass: HomeAssistant) -> None:
    """Test the presence sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=GVH5127_ABSENT_SERVICE_INFO.address,
        data={CONF_DEVICE_TYPE: "H5127"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    inject_bluetooth_service_info(hass, GVH5127_ABSENT_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 2

    motion_sensor = hass.states.get("binary_sensor.h51275e3f_motion")
    assert motion_sensor.state == STATE_OFF
    occupancy_sensor = hass.states.get("binary_sensor.h51275e3f_occupancy")
    assert occupancy_sensor.state == STATE_OFF

    inject_bluetooth_service_info(hass, GVH5127_PRESENT_SERVICE_INFO)
    await hass.async_block_till_done()

    motion_sensor = hass.states.get("binary_sensor.h51275e3f_motion")
    assert motion_sensor.state == STATE_OFF
    occupancy_sensor = hass.states.get("binary_sensor.h51275e3f_occupancy")
    assert occupancy_sensor.state == STATE_ON

    inject_bluetooth_service_info(hass, GVH5127_MOTION_SERVICE_INFO)
    await hass.async_block_till_done()

    motion_sensor = hass.states.get("binary_sensor.h51275e3f_motion")
    assert motion_sensor.state == STATE_ON
    occupancy_sensor = hass.states.get("binary_sensor.h51275e3f_occupancy")
    assert occupancy_sensor.state == STATE_ON
