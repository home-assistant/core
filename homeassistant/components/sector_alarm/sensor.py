"""The Sector Alarm Integration."""
from datetime import timedelta
import logging

from homeassistant.components.sector_alarm import DOMAIN as SECTOR_DOMAIN
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

UPDATE_INTERVAL = timedelta(minutes=5)

DEPENDENCIES = ["sector_alarm"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Initialition of the platform."""
    sector_connection = hass.data.get(SECTOR_DOMAIN)

    temps = sector_connection.GetTemps()

    dev = []

    for temp in temps:
        dev.append(SectorTempSensor(temp, sector_connection))

    async_add_entities(dev)


class SectorTempSensor(Entity):
    """Secotor Alarm temperature class."""

    def __init__(self, temp, sectorconnection):
        """Initialize the sensor."""
        self._sector = sectorconnection
        self._state = None
        self._name = temp[0]
        self._state = temp[1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @Throttle(UPDATE_INTERVAL)
    def update(self):
        """Update function for the temp sensor."""
        temps = self._sector.GetTemps()
        for name, temp in temps:
            if name == self._name:
                self._state = temp
