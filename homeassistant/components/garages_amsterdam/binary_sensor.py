"""Binary Sensor platform for Garages Amsterdam."""
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinator
from .const import ATTRIBUTION

BINARY_SENSORS = {
    "state",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass)

    async_add_entities(
        GaragesamsterdamBinarySensor(
            coordinator, config_entry.data["garage_name"], info_type
        )
        for info_type in BINARY_SENSORS
    )


class GaragesamsterdamBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary Sensor representing garages amsterdam data."""

    def __init__(self, coordinator, garage_name, info_type):
        """Initialize garages amsterdam binary sensor."""
        super().__init__(coordinator)
        self._unique_id = f"{garage_name}-{info_type}"
        self._garage_name = garage_name
        self._info_type = info_type
        self._name = garage_name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the device."""
        return self._unique_id

    @property
    def is_on(self):
        """If the binary sensor is currently on or off."""
        return (
            getattr(self.coordinator.data[self._garage_name], self._info_type) != "ok"
        )

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return DEVICE_CLASS_PROBLEM

    @property
    def device_state_attributes(self):
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
