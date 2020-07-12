"""Platform for sensor integration."""
import logging

from homeassistant.const import TEMP_CELSIUS

from . import SmartTubEntity
from .const import DOMAIN, SMARTTUB_API

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SmartTub sensors."""

    api = hass.data[DOMAIN][entry.unique_id][SMARTTUB_API]

    entities = []
    for spa_id in api.spa_ids:
        entities.extend(
            [
                SmartTubTargetWaterTemperature(api, spa_id),
                SmartTubCurrentWaterTemperature(api, spa_id),
                SmartTubHeaterStatus(api, spa_id),
            ]
        )

    async_add_entities(entities)


class SmartTubTargetWaterTemperature(SmartTubEntity):
    """The target water temperature for the spa."""

    def __init__(self, api, spa_id):
        """Initialize the sensor."""
        super().__init__(api, spa_id, "target water temperature")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.api.get_target_water_temperature(self.spa_id)

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

    def __init__(self, api, spa_id):
        """Initialize the sensor."""
        super().__init__(api, spa_id, "current water temperature")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.api.get_current_water_temperature(self.spa_id)

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

    def __init__(self, api, spa_id):
        """Initialize the sensor."""
        super().__init__(api, spa_id, "heater status")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.api.get_heater_status(self.spa_id)
