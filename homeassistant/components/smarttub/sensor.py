"""Platform for sensor integration."""
import logging

from homeassistant.const import TEMP_CELSIUS

from . import SmartTubEntity
from .const import DOMAIN, SMARTTUB_CONTROLLER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SmartTub sensors."""

    controller = hass.data[DOMAIN][entry.unique_id][SMARTTUB_CONTROLLER]

    entities = []
    for spa_id in controller.spa_ids:
        entities.extend(
            [
                SmartTubTargetWaterTemperature(controller, spa_id),
                SmartTubCurrentWaterTemperature(controller, spa_id),
                SmartTubHeaterStatus(controller, spa_id),
            ]
        )

    async_add_entities(entities)


class SmartTubTargetWaterTemperature(SmartTubEntity):
    """The target water temperature for the spa."""

    def __init__(self, controller, spa_id):
        """Initialize the sensor."""
        super().__init__(controller, spa_id, "target water temperature")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.controller.get_target_water_temperature(self.spa_id)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return "temperature"


class SmartTubCurrentWaterTemperature(SmartTubEntity):
    """The current water temperature for the spa."""

    def __init__(self, controller, spa_id):
        """Initialize the sensor."""
        super().__init__(controller, spa_id, "current water temperature")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.controller.get_current_water_temperature(self.spa_id)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_class(self) -> str:
        """Return the class of this device."""
        return "temperature"


class SmartTubHeaterStatus(SmartTubEntity):
    """The state of the heater."""

    def __init__(self, controller, spa_id):
        """Initialize the sensor."""
        super().__init__(controller, spa_id, "heater status")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.controller.get_heater_status(self.spa_id)
