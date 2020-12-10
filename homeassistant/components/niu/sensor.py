"""Platform for sensor integration."""
import logging

from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config, async_add_entities):
    """Set up the sensor platform."""

    entities = []

    # Get Niu Api Object
    niuApi = hass.data[DOMAIN][config.entry_id]

    # Get all scooters from Niu API
    await niuApi.update_vehicles()
    for sn, veh in niuApi.get_vehicles().items():
        _LOGGER.warning("Found vehicle: %s", veh.name)

        # Awesome! Now use Nissan Leaf as example to create all different sensors

    entities.append(ExampleSensor())

    async_add_entities(entities, True)

    return True


class ExampleSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Example Temperature"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self._state = 23