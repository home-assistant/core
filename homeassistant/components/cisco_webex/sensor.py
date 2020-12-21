"""Platform for sensor integration."""
import logging

from homeassistant.components.binary_sensor import DEVICE_CLASS_PRESENCE, Entity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_EMAIL
from homeassistant.helpers.typing import HomeAssistantType

from .const import API, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import the platform into a config entry."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Webex sensor based on a config entry."""

    webex_domain_data = hass.data[DOMAIN][config_entry.entry_id]
    config = config_entry.data

    async_add_entities(
        [
            WebexPresenceSensor(
                api=webex_domain_data[API],
                email=config[CONF_EMAIL],
                name=f"{DEFAULT_NAME} {config[CONF_EMAIL]}",
            )
        ]
    )


class WebexPresenceSensor(Entity):
    """Representation of a Webex Presence Sensor."""

    def __init__(self, api, email, name):
        """Initialize the sensor."""
        self._state = None
        self._user_id = None
        self._email = email
        self._attributes = {}
        self._api = api
        self._name = name
        self.uid = f"webex_status_{email}"

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
        self._attributes["on_a_call"] = self._state in ["call", "meeting", "presenting"]
        return self._attributes

    @property
    def device_class(self):
        """Return the device class of this binary sensor."""
        return DEVICE_CLASS_PRESENCE

    @property
    def unique_id(self):
        """Return a unique id identifying the entity."""
        self.uid

    def update(self):
        """Update device state."""
        if self._user_id is None:

            people_list = list(self._api.people.list(email=self._email))
            if len(people_list) > 0:
                person = people_list[0]
                self._user_id = person.id
                self.update_with_data(person)
                _LOGGER.debug(
                    "WebexPresenceSensor init with _user_id: %s", self._user_id
                )
            else:
                _LOGGER.error("Cannot find any Webex user with email: %s", self._email)
                return

        self.update_with_data(self._api.people.get(self._user_id))

    def update_with_data(self, person):
        """Update local data with the latest person."""
        self._attributes = person.to_dict()
        # available states documented here
        # https://developer.webex.com/docs/api/v1/people/list-people
        self._state = person.status
        _LOGGER.debug("WebexPeopleSensor person state: %s", self._state)
