"""Support for Avri waste curbside collection pickup."""
from datetime import timedelta
import logging

from avri.api import Avri, AvriException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
CONF_COUNTRY_CODE = "country_code"
CONF_ZIP_CODE = "zip_code"
CONF_HOUSE_NUMBER = "house_number"
CONF_HOUSE_NUMBER_EXTENSION = "house_number_extension"
DEFAULT_NAME = "avri"
ICON = "mdi:trash-can-outline"
SCAN_INTERVAL = timedelta(hours=4)
DEFAULT_COUNTRY_CODE = "NL"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ZIP_CODE): cv.string,
        vol.Required(CONF_HOUSE_NUMBER): cv.positive_int,
        vol.Optional(CONF_HOUSE_NUMBER_EXTENSION): cv.string,
        vol.Optional(CONF_COUNTRY_CODE, default=DEFAULT_COUNTRY_CODE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Avri Waste platform."""
    client = Avri(
        postal_code=config[CONF_ZIP_CODE],
        house_nr=config[CONF_HOUSE_NUMBER],
        house_nr_extension=config.get(CONF_HOUSE_NUMBER_EXTENSION),
        country_code=config[CONF_COUNTRY_CODE],
    )

    try:
        each_upcoming = client.upcoming_of_each()
    except AvriException as ex:
        raise PlatformNotReady from ex
    else:
        entities = [
            AvriWasteUpcoming(config[CONF_NAME], client, upcoming.name)
            for upcoming in each_upcoming
        ]
        add_entities(entities, True)


class AvriWasteUpcoming(Entity):
    """Avri Waste Sensor."""

    def __init__(self, name: str, client: Avri, waste_type: str):
        """Initialize the sensor."""
        self._waste_type = waste_type
        self._name = f"{name}_{self._waste_type}"
        self._state = None
        self._client = client
        self._state_available = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return (
            f"{self._waste_type}"
            f"-{self._client.country_code}"
            f"-{self._client.postal_code}"
            f"-{self._client.house_nr}"
            f"-{self._client.house_nr_extension}"
        )

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._state_available

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    def update(self):
        """Update device state."""
        try:
            pickup_events = self._client.upcoming_of_each()
        except AvriException as ex:
            _LOGGER.error(
                "There was an error retrieving upcoming garbage pickups: %s", ex
            )
            self._state_available = False
            self._state = None
        else:
            self._state_available = True
            matched_events = list(
                filter(lambda event: event.name == self._waste_type, pickup_events)
            )
            if not matched_events:
                self._state = None
            else:
                self._state = matched_events[0].day.date()
