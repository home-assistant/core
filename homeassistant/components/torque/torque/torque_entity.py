import logging
from random import randint
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from homeassistant.core import callback
from .const import DOMAIN
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNAVAILABLE

_LOGGER = logging.getLogger(__name__)

class TorqueEntity(CoordinatorEntity, Entity):
    def __init__(self, hass, coordinator, device_id, pid, name, unit, icon):
        super().__init__(coordinator)

        self._hass = hass
        self._device_id = device_id
        self._pid = pid
        self._name = name
        self._unit = unit
        self._icon = icon

        self.data = hass.data[DOMAIN][coordinator._entry.entry_id]

        self._state = STATE_UNAVAILABLE

        self._unique_id = slugify(f"{device_id}_{pid}")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        unit = self.coordinator.default_sensor_units[self._pid]
        if self._pid in self.coordinator.custom_units.keys():
            unit = self.coordinator.custom_units[self._pid]
        return unit


    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device_id)}
        }

    @property
    def entity_category(self):
        return None

    @property
    def icon(self):
        """Return the default icon of the sensor."""
        return self._icon

    def _get_car_value(self, pid):
        return self.data.values[pid]

    @callback
    def async_on_update(self, value):
        """Receive an update."""
        self._state = value
        self.async_write_ha_state()



