"""
Support for Mobile Vikings (in Poland).

Get data from "My account" page:
https://mobilevikings.pl/en/mysims
"""
from homeassistant.const import DATA_GIGABYTES
from homeassistant.helpers.entity import Entity


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    add_entities([VikingSensor()])


class VikingSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._icon = "mdi:cellphone"
        self._number = "666999666"
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Mobile Vikings"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return DATA_GIGABYTES

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {"number": self._number}

    def update(self):
        """Fetch new state data for the sensor."""
        self._state = 23
