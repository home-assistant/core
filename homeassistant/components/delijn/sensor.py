"""Support for De Lijn (Flemish public transport) information."""
import logging

from pydelijn.api import Passages
from pydelijn.common import HttpException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_API_KEY, DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by data.delijn.be"

CONF_NEXT_DEPARTURE = "next_departure"
CONF_STOP_ID = "stop_id"
CONF_NUMBER_OF_DEPARTURES = "number_of_departures"

DEFAULT_NAME = "De Lijn"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STOP_ID): cv.string,
                vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=5): cv.positive_int,
            }
        ],
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    api_key = config[CONF_API_KEY]

    session = async_get_clientsession(hass)

    sensors = []
    for nextpassage in config[CONF_NEXT_DEPARTURE]:
        sensors.append(
            DeLijnPublicTransportSensor(
                Passages(
                    hass.loop,
                    nextpassage[CONF_STOP_ID],
                    nextpassage[CONF_NUMBER_OF_DEPARTURES],
                    api_key,
                    session,
                    True,
                )
            )
        )

    async_add_entities(sensors, True)


class DeLijnPublicTransportSensor(SensorEntity):
    """Representation of a Ruter sensor."""

    def __init__(self, line):
        """Initialize the sensor."""
        self.line = line
        self._attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._name = None
        self._state = None
        self._available = True

    async def async_update(self):
        """Get the latest data from the De Lijn API."""
        try:
            await self.line.get_passages()
            self._name = await self.line.get_stopname()
        except HttpException:
            self._available = False
            _LOGGER.error("De Lijn http error")
            return

        self._attributes["stopname"] = self._name

        try:
            first = self.line.passages[0]
            if first["due_at_realtime"] is not None:
                first_passage = first["due_at_realtime"]
            else:
                first_passage = first["due_at_schedule"]
            self._state = first_passage
            self._attributes["line_number_public"] = first["line_number_public"]
            self._attributes["line_transport_type"] = first["line_transport_type"]
            self._attributes["final_destination"] = first["final_destination"]
            self._attributes["due_at_schedule"] = first["due_at_schedule"]
            self._attributes["due_at_realtime"] = first["due_at_realtime"]
            self._attributes["is_realtime"] = first["is_realtime"]
            self._attributes["next_passages"] = self.line.passages
            self._available = True
        except (KeyError, IndexError):
            _LOGGER.error("Invalid data received from De Lijn")
            self._available = False

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:bus"

    @property
    def extra_state_attributes(self):
        """Return attributes for the sensor."""
        return self._attributes
