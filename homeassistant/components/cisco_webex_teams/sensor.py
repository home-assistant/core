"""Platform for sensor integration."""
import logging
import voluptuous as vol
from webexteamssdk import WebexTeamsAPI

from homeassistant.const import CONF_TOKEN, CONF_EMAIL, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PRESENCE,
    PLATFORM_SCHEMA,
    Entity
)

DEFAULT_NAME = "Webex Presence"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_EMAIL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    api = WebexTeamsAPI(access_token=config[CONF_TOKEN])
    # Validate the token and email work as expected
    people_list = list(api.people.list(email=config[CONF_EMAIL]))
    if len(people_list) > 0:
        person = people_list[0]
        name = f"{DEFAULT_NAME} {config[CONF_EMAIL]}" if config[CONF_NAME] == DEFAULT_NAME else DEFAULT_NAME
        add_entities([WebexPresenceSensor(
            api=api,
            person=person,
            name=name)
        ])
    else:
        _LOGGER.error("Cannot find any Webex user with email: %s", config[CONF_EMAIL])
        return


class WebexPresenceSensor(Entity):
    """Representation of a Webex Presence Sensor."""

    def __init__(self, api, person, name):
        """Initialize the sensor."""
        self._state = None
        self._attributes = {}
        self._api = api
        self._user_id = person.id
        self._name = name

        self.update_with_data(person)

        _LOGGER.debug("WebexPresenceSensor init with _user_id: %s", self._user_id)

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def state(self):
        """Return the status of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def device_class(self):
        """Return the device class of this binary sensor."""
        return DEVICE_CLASS_PRESENCE

    def update(self):
        """Update device state."""
        self.update_with_data(self._api.people.get(self._user_id))

    def update_with_data(self, person):
        """Update local data with the latest person."""
        self._attributes = person.to_dict()
        # available states documented here
        # https://developer.webex.com/docs/api/v1/people/list-people
        self._state = person.status
        _LOGGER.debug("WebexPeopleSensor person state: %s", self._state)
