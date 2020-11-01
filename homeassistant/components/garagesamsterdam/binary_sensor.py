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
            coordinator, config_entry.data["garageName"], info_type
        )
        for info_type in BINARY_SENSORS
    )


class GaragesamsterdamBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary Sensor representing garages amsterdam data."""

    name = None
    unique_id = None

    def __init__(self, coordinator, garageName, info_type):
        """Initialize garages amsterdam binary sensor."""
        super().__init__(coordinator)
        self.name = f"{coordinator.data[garageName].garageName} - {info_type}"
        self.unique_id = f"{garageName}-{info_type}"
        self.garageName = garageName
        self.info_type = info_type

    @property
    def is_on(self):
        """If the binary sensor is currently on or off."""
        if getattr(self.coordinator.data[self.garageName], self.info_type) == "ok":
            return False
        else:
            return True

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return DEVICE_CLASS_PROBLEM

    @property
    def device_state_attributes(self):
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
