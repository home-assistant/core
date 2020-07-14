"""Support for the growatt_rs232 service."""

import logging

from growattRS232.const import ATTR_FIRMWARE, ATTR_MODEL_NUMBER, ATTR_SERIAL_NUMBER

from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.helpers.entity import Entity

from .const import ATTR_LABEL, DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add growatt_rs232 entities from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = []

    device_info = {
        "identifiers": {(DOMAIN, coordinator.data.get(ATTR_SERIAL_NUMBER, ""))},
        "manufacturer": "Growatt",
        "model": coordinator.data.get(ATTR_MODEL_NUMBER, ""),
        "firmware": coordinator.data.get(ATTR_FIRMWARE, ""),
    }

    for sensor in SENSOR_TYPES:
        if sensor in coordinator.data:
            sensors.append(GrowattRS232Sensor(coordinator, sensor, device_info))
    async_add_entities(sensors, False)


class GrowattRS232Sensor(Entity):
    """Define a Growatt_RS232 sensor."""

    def __init__(self, coordinator, kind, device_info):
        """Initialize."""
        self._name = f"{coordinator.data[ATTR_SERIAL_NUMBER]} \
            {SENSOR_TYPES[kind][ATTR_LABEL]}"
        self._unique_id = f"{coordinator.data[ATTR_SERIAL_NUMBER].lower()}_{kind}"
        self._device_info = device_info
        self.coordinator = coordinator
        self.kind = kind
        self._attrs = {}

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data.get(self.kind)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self.kind][ATTR_ICON]

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._unique_id

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.kind][ATTR_UNIT_OF_MEASUREMENT]

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self):
        """No need to poll. Coordinator notifies entity of updates."""
        return False

    @property
    def device_info(self):
        """Return the device info."""
        return self._device_info

    @property
    def entity_registry_enabled_default(self):
        """Return if entity should be enabled when first added to entity registry."""
        return True

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self):
        """Update GrowattRS232Sensor entity."""
        await self.coordinator.async_request_refresh()
