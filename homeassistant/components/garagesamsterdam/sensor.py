"""Sensor platform for Garages Amsterdam."""
import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import get_coordinator
from .const import ATTRIBUTION

SENSORS = {
    "free_space_short": "mdi:car",
    "free_space_long": "mdi:car",
    "short_capacity": "mdi:car",
    "long_capacity": "mdi:car",
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Defer sensor setup to the shared sensor module."""
    coordinator = await get_coordinator(hass)

    async_add_entities(
        GaragesamsterdamSensor(coordinator, config_entry.data["garage_name"], info_type)
        for info_type in SENSORS
    )


class GaragesamsterdamSensor(CoordinatorEntity):
    """Sensor representing garages amsterdam data."""

    unique_id = None

    def __init__(self, coordinator, garage_name, info_type):
        """Initialize garages amsterdam sensor."""
        super().__init__(coordinator)
        self.unique_id = f"{garage_name}-{info_type}"
        self.garage_name = garage_name
        self.info_type = info_type
        self._name = f"{self.coordinator.data[self.garage_name].garage_name} - {self.info_type}".replace(
            "_", " "
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self):
        """Return if sensor is available."""
        return self.coordinator.last_update_success and (
            self.garage_name in self.coordinator.data
        )

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        if getattr(self.coordinator.data[self.garage_name], self.info_type) != "":
            return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self.coordinator.data[self.garage_name], self.info_type)

    @property
    def icon(self):
        """Return the icon."""
        return SENSORS[self.info_type]

    @property
    def unit_of_measurement(self):
        """Return unit of measurement."""
        return "cars"

    @property
    def device_state_attributes(self):
        """Return device attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}
