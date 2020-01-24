"""Support for Avri waste curbside collection pickup."""
import logging

from avri.api import Avri, AvriException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
CONF_COUNTRY_CODE = "country_code"
CONF_POSTCODE = "postcode"
CONF_HOUSE_NUMBER = "house_number"
CONF_HOUSE_NUMBER_EXTENSION = "house_number_extension"
DEFAULT_NAME = "avri"
ICON = "mdi:trash-can-outline"
SCAN_INTERVAL = 86400

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_POSTCODE): cv.string,
        vol.Required(CONF_HOUSE_NUMBER): cv.string,
        vol.Optional(CONF_HOUSE_NUMBER_EXTENSION, default=''): cv.string,
        vol.Optional(CONF_COUNTRY_CODE, default='NL'): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Avri Waste platform."""
    client = Avri(
        postal_code=config[CONF_POSTCODE],
        house_nr=config[CONF_HOUSE_NUMBER],
        house_nr_extension=config[CONF_HOUSE_NUMBER_EXTENSION],
        country_code=config[CONF_COUNTRY_CODE]
    )

    try:
        each_upcoming = client.upcoming_of_each()
        _LOGGER.info(f'avri: {each_upcoming}')
    except AvriException as ex:
        _LOGGER.error("Avri platform error.", ex)
        return
    else:
        for upcoming in each_upcoming:
            add_entities([AvriWasteUpcoming(config[CONF_NAME], client, upcoming.name)], True)


class AvriWasteUpcoming(Entity):
    """Avri Waste Sensor."""

    def __init__(self, name: str, client: Avri, waste_type: str):
        """Initialize the sensor."""
        self._waste_type = waste_type
        self._name = f"{name}_{self._waste_type}"
        self._state = None
        self.client = client

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return (f"{self.name}"
                f"{self.client.country_code}{self.client.postal_code}"
                f"{self.client.house_nr}{self.client.house_nr_extension}")

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return ICON

    def update(self):
        """Update device state."""
        try:
            pickup_events = self.client.upcoming_of_each()
            if len(pickup_events) == 0:
                return
            for event in pickup_events:
                if event.name == self._waste_type:
                    self._state = event.day.date()
                    break
            else:
                self._state = None
        except AvriException as ex:
            _LOGGER.error("Avri platform error.", ex)
