"""
Support for tracking people.

For more details about this component, please refer to the documentation.
https://home-assistant.io/components/person/
"""
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN)
from homeassistant.const import (
    ATTR_ID, ATTR_LATITUDE, ATTR_LONGITUDE, CONF_ID, CONF_NAME)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)
ATTR_SOURCE = 'source'
ATTR_USER_ID = 'user_id'
CONF_DEVICE_TRACKERS = 'device_trackers'
CONF_USER_ID = 'user_id'
DOMAIN = 'person'
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

PERSON_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_USER_ID): cv.string,
    vol.Optional(CONF_DEVICE_TRACKERS, default=[]): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)),
})

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.All(cv.ensure_list, [PERSON_SCHEMA])
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the person component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    conf = config.get(DOMAIN, [])
    entities = []
    seen_ids = set()

    for person_conf in conf:
        person_id = person_conf[CONF_ID]

        if person_id in seen_ids:
            _LOGGER.error("Found user with duplicate ID.")
            continue

        # We are going to track the ID as seen, even if they might be skipped
        # because of an invalid user id. That way we have predictable behavior
        # if users are added/removed.
        seen_ids.add(person_id)

        user_id = person_conf.get(CONF_USER_ID)

        if (user_id is not None
                and await hass.auth.async_get_user(user_id) is None):
            _LOGGER.error(
                "Invalid user_id detected for person %s",
                person_conf[CONF_NAME])
            continue

        entities.append(Person(person_conf, False))

    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    data = await store.async_load()

    if data is not None:
        for person_conf in data['persons']:
            person_id = person_conf[CONF_ID]

            if person_id in seen_ids:
                _LOGGER.error("Found storage user with duplicate ID.")
                continue

            seen_ids.add(person_id)

            entities.append(Person(person_conf, True))

    if entities:
        await component.async_add_entities(entities)

    return True


class Person(RestoreEntity):
    """Represent a tracked person."""

    def __init__(self, config, editable):
        """Set up person."""
        self._config = config
        self._latitude = None
        self._longitude = None
        self._name = config[CONF_NAME]
        self._source = None
        self._state = None
        self._trackers = config.get(CONF_DEVICE_TRACKERS)
        self._user_id = config.get(CONF_USER_ID)
        self._editable = editable

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def state(self):
        """Return the state of the person."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes of the person."""
        data = {}
        data[ATTR_ID] = self.unique_id
        if self._latitude is not None:
            data[ATTR_LATITUDE] = round(self._latitude, 5)
        if self._longitude is not None:
            data[ATTR_LONGITUDE] = round(self._longitude, 5)
        if self._source is not None:
            data[ATTR_SOURCE] = self._source
        if self._user_id is not None:
            data[ATTR_USER_ID] = self._user_id
        return data

    @property
    def unique_id(self):
        """Return a unique ID for the person."""
        return self._config[CONF_ID]

    async def async_added_to_hass(self):
        """Register device trackers."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._parse_source_state(state)

        trackers = self._config.get(CONF_DEVICE_TRACKERS)

        if not trackers:
            return

        @callback
        def async_handle_tracker_update(entity, old_state, new_state):
            """Handle the device tracker state changes."""
            self._parse_source_state(new_state)
            self.async_schedule_update_ha_state()

        _LOGGER.debug(
            "Subscribe to device trackers for %s", self.entity_id)

        async_track_state_change(
            self.hass, trackers, async_handle_tracker_update)

    def _parse_source_state(self, state):
        """Parse source state and set person attributes."""
        self._state = state.state
        self._source = state.entity_id
        self._latitude = state.attributes.get(ATTR_LATITUDE)
        self._longitude = state.attributes.get(ATTR_LONGITUDE)
