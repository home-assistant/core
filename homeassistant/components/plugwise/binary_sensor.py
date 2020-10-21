"""Plugwise Binary Sensor component for Home Assistant."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import callback

from .const import (
    COORDINATOR,
    DOMAIN,
    FLAME_ICON,
    FLOW_OFF_ICON,
    FLOW_ON_ICON,
    IDLE_ICON,
)
from .sensor import SmileSensor

BINARY_SENSOR_MAP = {
    "dhw_state": ["Domestic Hot Water State", None],
    "slave_boiler_state": ["Secondary Heater Device State", None],
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smile binary_sensors from a config entry."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]

    entities = []

    all_devices = api.get_all_devices()
    for dev_id, device_properties in all_devices.items():
        if device_properties["class"] != "heater_central":
            continue

        data = api.get_device_data(dev_id)
        for binary_sensor, dummy in BINARY_SENSOR_MAP.items():
            if binary_sensor not in data:
                continue

            entities.append(
                PwBinarySensor(
                    api,
                    coordinator,
                    device_properties["name"],
                    binary_sensor,
                    dev_id,
                    device_properties["class"],
                )
            )

    async_add_entities(entities, True)


class PwBinarySensor(SmileSensor, BinarySensorEntity):
    """Representation of a Plugwise binary_sensor."""

    def __init__(self, api, coordinator, name, binary_sensor, dev_id, model):
        """Set up the Plugwise API."""
        super().__init__(api, coordinator, name, dev_id, binary_sensor)

        self._binary_sensor = binary_sensor

        self._is_on = False
        self._icon = None

        self._unique_id = f"{dev_id}-{binary_sensor}"

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @callback
    def _async_process_data(self):
        """Update the entity."""
        data = self._api.get_device_data(self._dev_id)

        if not data:
            _LOGGER.error("Received no data for device %s", self._binary_sensor)
            self.async_write_ha_state()
            return

        if self._binary_sensor not in data:
            self.async_write_ha_state()
            return

        self._is_on = data[self._binary_sensor]

        self._state = STATE_OFF
        if self._binary_sensor == "dhw_state":
            self._icon = FLOW_OFF_ICON
        if self._binary_sensor == "slave_boiler_state":
            self._icon = IDLE_ICON
        if self._is_on:
            self._state = STATE_ON
            if self._binary_sensor == "dhw_state":
                self._icon = FLOW_ON_ICON
            if self._binary_sensor == "slave_boiler_state":
                self._icon = FLAME_ICON

        self.async_write_ha_state()
