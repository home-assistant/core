"""Support for Recollect Waste curbside collection pickup."""
from datetime import date, timedelta
import logging

from aiorecollect import Client
from aiorecollect.errors import RecollectError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
ATTR_PICKUP_TYPES = "pickup_types"
ATTR_AREA_NAME = "area_name"
ATTR_NEXT_PICKUP_TYPES = "next_pickup_types"
ATTR_NEXT_PICKUP_DATE = "next_pickup_date"
CONF_PLACE_ID = "place_id"
CONF_SERVICE_ID = "service_id"
DEFAULT_NAME = "recollect_waste"
ICON = "mdi:trash-can-outline"
SCAN_INTERVAL = timedelta(days=1)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PLACE_ID): cv.string,
        vol.Required(CONF_SERVICE_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Recollect Waste platform."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = Client(config[CONF_PLACE_ID], config[CONF_SERVICE_ID], session=session)

    # Ensure the client can connect to the API successfully
    # with given place_id and service_id.
    try:
        await client.async_get_next_pickup_event()
    except RecollectError as err:
        _LOGGER.error("Error setting up Recollect sensor platform: %s", err)
        return

    async_add_entities([RecollectWasteSensor(config.get(CONF_NAME), client)], True)


class RecollectWasteSensor(Entity):
    """Recollect Waste Sensor."""

    def __init__(self, name, client):
        """Initialize the sensor."""
        self._attributes = {}
        self._name = name
        self._state = None
        self.client = client

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.client.place_id}{self.client.service_id}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    async def async_update(self):
        """Update device state."""
        try:
            pickup_event_array = await self.client.async_get_pickup_events(
                start_date=date.today(), end_date=date.today() + timedelta(weeks=4)
            )
        except RecollectError as err:
            _LOGGER.error("Error while requesting data from Recollect: %s", err)
            return

        pickup_event = pickup_event_array[0]
        next_pickup_event = pickup_event_array[1]
        next_date = str(next_pickup_event.date)
        self._state = pickup_event.date
        self._attributes.update(
            {
                ATTR_PICKUP_TYPES: pickup_event.pickup_types,
                ATTR_AREA_NAME: pickup_event.area_name,
                ATTR_NEXT_PICKUP_TYPES: next_pickup_event.pickup_types,
                ATTR_NEXT_PICKUP_DATE: next_date,
            }
        )
