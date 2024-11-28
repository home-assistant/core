"""Support for Victron Venus sensors.

This module is light-weight and only registers the sensors with Home Assistant. The sensor class is implemented in the victronvenus_sensor module.
"""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .victronvenus_base import VictronVenusConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VictronVenusConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Victron Venus sensors from a config entry."""

    hub = config_entry.runtime_data

    devices = hub.victron_devices

    for device in devices:
        sensors = device.victron_sensors
        for sensor in sensors:
            async_add_entities([sensor])
            sensor.mark_registered_with_homeassistant()
