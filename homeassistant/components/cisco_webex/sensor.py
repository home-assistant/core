"""Platform for sensor integration."""
import logging

from homeassistant.components.binary_sensor import DEVICE_CLASS_PRESENCE, Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.helpers.typing import HomeAssistantType

from .const import API, DEFAULT_SENSOR_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Webex sensor based on a config entry."""

    webex_domain_data = hass.data[DOMAIN][config_entry.unique_id]
    config = config_entry.data

    async_add_entities(
        [
            WebexPresenceSensor(
                api=webex_domain_data[API],
                email=config[CONF_EMAIL],
                name=f"{DEFAULT_SENSOR_NAME} {config[CONF_EMAIL]}",
            )
        ]
    )


class WebexPresenceSensor(Entity):
    """Representation of a Webex Presence Sensor."""

    def __init__(self, api, email, name):
        """Initialize the sensor."""
        self._status = None
        self._user_id = None
        self._email = email
        self._attributes = {}
        self._api = api
        self._name = name
        self._avatar = None

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def state(self):
        """Return the status of the binary sensor."""
        return self._status

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attributes["on_a_call"] = self._status in [
            "call",
            "meeting",
            "presenting",
        ]
        return self._attributes

    @property
    def device_class(self):
        """Return the device class of this binary sensor."""
        return DEVICE_CLASS_PRESENCE

    @property
    def unique_id(self):
        """Return a unique id identifying the entity."""
        return f"webex_sensor_{self._email}"

    @property
    def device_info(self):
        """Device info."""
        return {
            "name": self._name,
            "identifiers": {(DOMAIN,)},
            "manufacturer": "Cisco",
            "model": "Webex.com",
            "default_name": "Webex.com",
            "entry_type": "service",
        }

    @property
    def entity_picture(self):
        """Avatar of the account."""
        return self._avatar

    def update(self):
        """Update device state."""
        if self._user_id is None:
            # First, get the user ID
            person = next(iter(self._api.people.list(email=self._email)), None)
            if person is not None:
                self._user_id = person.id
                self._name = f"Webex {person.displayName}"

                self.update_with_data(person)
                _LOGGER.debug("%s user id: %s", self._email, self._user_id)
            else:
                _LOGGER.error("Cannot find any Webex user with email: %s", self._email)
                return

        self.update_with_data(self._api.people.get(self._user_id))

    def update_with_data(self, person):
        """Update local data with the latest person."""
        self._attributes = person.to_dict()
        # available status documented here
        # https://developer.webex.com/docs/api/v1/people/list-people
        self._status = person.status
        self._avatar = person.avatar
        _LOGGER.debug("%s state: %s", self._email, self._status)
