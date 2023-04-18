"""Test the Melnor sensors."""
from __future__ import annotations

from freezegun import freeze_time

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .conftest import (
    mock_config_entry,
    mock_melnor_device,
    patch_async_ble_device_from_address,
    patch_async_register_callback,
    patch_melnor_device,
)

from tests.common import async_fire_time_changed


async def test_battery_sensor(hass: HomeAssistant) -> None:
    """Test the battery sensor."""

    entry = mock_config_entry(hass)

    with patch_async_ble_device_from_address(), patch_melnor_device(), patch_async_register_callback():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        battery_sensor = hass.states.get("sensor.test_melnor_battery")
        assert battery_sensor.state == "80"
        assert battery_sensor.attributes["unit_of_measurement"] == PERCENTAGE
        assert battery_sensor.attributes["device_class"] == SensorDeviceClass.BATTERY
        assert battery_sensor.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_minutes_remaining_sensor(hass: HomeAssistant) -> None:
    """Test the minutes remaining sensor."""

    now = dt_util.utcnow()

    entry = mock_config_entry(hass)
    device = mock_melnor_device()

    end_time = now + dt_util.dt.timedelta(minutes=10)

    # we control this mock

    device.zone1._end_time = (end_time).timestamp()

    with freeze_time(now), patch_async_ble_device_from_address(), patch_melnor_device(
        device
    ), patch_async_register_callback():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Valve is off, report 0
        minutes_sensor = hass.states.get("sensor.zone_1_manual_cycle_end")
        assert minutes_sensor.state == "unknown"
        assert minutes_sensor.attributes["device_class"] == SensorDeviceClass.TIMESTAMP

        # Turn valve on
        device.zone1._is_watering = True

        async_fire_time_changed(hass, now + dt_util.dt.timedelta(seconds=10))
        await hass.async_block_till_done()

        # Valve is on, report 10
        minutes_remaining_sensor = hass.states.get("sensor.zone_1_manual_cycle_end")
        assert minutes_remaining_sensor.state == end_time.isoformat(timespec="seconds")


async def test_rssi_sensor(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the rssi sensor."""

    entry = mock_config_entry(hass)

    device = mock_melnor_device()

    with patch_async_ble_device_from_address(), patch_melnor_device(
        device
    ), patch_async_register_callback():
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = f"sensor.{device.name}_rssi"

        # Ensure the entity is disabled by default by checking the registry

        rssi_registry_entry = entity_registry.async_get(entity_id)

        assert rssi_registry_entry is not None
        assert rssi_registry_entry.disabled_by is not None

        # Enable the entity and assert everything else is working as expected
        entity_registry.async_update_entity(entity_id, disabled_by=None)

        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

        rssi = hass.states.get(entity_id)

        assert (
            rssi.attributes["unit_of_measurement"] == SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        )
        assert rssi.attributes["device_class"] == SensorDeviceClass.SIGNAL_STRENGTH
        assert rssi.attributes["state_class"] == SensorStateClass.MEASUREMENT
