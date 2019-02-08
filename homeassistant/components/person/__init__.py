"""
Support for tracking people.

For more details about this component, please refer to the documentation.
https://home-assistant.io/components/person/
"""
from collections import OrderedDict
import logging
import uuid

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
from homeassistant.components import websocket_api
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)
ATTR_SOURCE = 'source'
ATTR_USER_ID = 'user_id'
CONF_DEVICE_TRACKERS = 'device_trackers'
CONF_USER_ID = 'user_id'
DOMAIN = 'person'
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
SAVE_DELAY = 10

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

_UNDEF = object()


class PersonManager:
    """Manage person data."""

    def __init__(self, hass: HomeAssistantType, component: EntityComponent,
                 config_persons):
        """Initialize person storage."""
        self.hass = hass
        self.component = component
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.storage_data = None

        config_data = self.config_data = OrderedDict()
        for conf in config_persons:
            person_id = conf[CONF_ID]

            if person_id in config_data:
                _LOGGER.error("Found config user with duplicate ID.")
                continue

            config_data[person_id] = conf

    @callback
    def list_persons(self):
        """Iterate the person manager."""
        yield from self.config_data.values()
        yield from self.storage_data.values()

    async def async_initialize(self):
        """Get the person data."""
        raw_storage = await self.store.async_load()

        if raw_storage is None:
            raw_storage = {
                'persons': []
            }

        storage_data = self.storage_data = OrderedDict()

        for person in raw_storage['persons']:
            storage_data[person[CONF_ID]] = person

        entities = []

        for person_conf in self.config_data.values():
            person_id = person_conf[CONF_ID]
            user_id = person_conf.get(CONF_USER_ID)

            if (user_id is not None
                    and await self.hass.auth.async_get_user(user_id) is None):
                _LOGGER.error(
                    "Invalid user_id detected for person %s", person_id)
                continue

            entities.append(Person(person_conf, False))

        for person_conf in storage_data.values():
            if person_conf[CONF_ID] in self.config_data:
                _LOGGER.error(
                    "Skipping adding person from storage with same ID as"
                    " configuration.yaml entry: %s.", person_id)
                continue

            entities.append(Person(person_conf, True))

        if entities:
            await self.component.async_add_entities(entities)

    async def async_create_person(self, *, name, device_trackers=None,
                                  user_id=None):
        """Create a new person."""
        person = {
            CONF_ID: uuid.uuid4().hex,
            CONF_NAME: name,
            CONF_USER_ID: user_id,
            CONF_DEVICE_TRACKERS: device_trackers,
        }
        self.storage_data[person[CONF_ID]] = person
        self._async_schedule_save()
        await self.component.async_add_entities([Person(person, True)])
        return person

    async def async_update_person(self, person_id, *, name=_UNDEF,
                                  device_trackers=_UNDEF, user_id=_UNDEF):
        """Update person."""
        if person_id not in self.storage_data:
            raise ValueError("Invalid person specified.")

        changes = {
            key: value for key, value in (
                ('name', name),
                ('device_trackers', device_trackers),
                ('user_id', user_id)
            ) if value is not _UNDEF
        }

        self.storage_data[person_id].update(changes)
        self._async_schedule_save()
        return self.storage_data[person_id]

    async def async_delete_person(self, person_id):
        """Delete person."""
        if person_id not in self.storage_data:
            raise ValueError("Invalid person specified.")

        self.storage_data.pop(person_id)
        self._async_schedule_save()

    @callback
    def _async_schedule_save(self) -> None:
        """Schedule saving the area registry."""
        self.store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict:
        """Return data of area registry to store in a file."""
        return {
            'persons': list(self.storage_data.values())
        }


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the person component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    conf_persons = config.get(DOMAIN, [])
    manager = hass.data[DOMAIN] = PersonManager(hass, component, conf_persons)
    await manager.async_initialize()

    websocket_api.async_register_command(hass, ws_list_person)
    websocket_api.async_register_command(hass, ws_create_person)
    websocket_api.async_register_command(hass, ws_update_person)
    websocket_api.async_register_command(hass, ws_delete_person)

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


@websocket_api.websocket_command({
    vol.Required('type'): 'person/list',
})
def ws_list_person(hass: HomeAssistantType,
                   connection: websocket_api.ActiveConnection, msg):
    """List persons."""
    manager = hass.data[DOMAIN]  # type: PersonManager
    connection.send_result(msg['id'], list(manager.list_persons()))


@websocket_api.websocket_command({
    vol.Required('type'): 'person/create',
    vol.Required('name'): str,
    vol.Optional('user_id'): vol.Any(str, None),
    vol.Optional('device_trackers', default=[]): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_create_person(hass: HomeAssistantType,
                           connection: websocket_api.ActiveConnection, msg):
    """Create a person."""
    manager = hass.data[DOMAIN]  # type: PersonManager
    person = await manager.async_create_person(
        name=msg['name'],
        user_id=msg.get('user_id'),
        device_trackers=msg['device_trackers']
    )
    connection.send_result(msg['id'], person)


@websocket_api.websocket_command({
    vol.Required('type'): 'person/update',
    vol.Required('person_id'): str,
    vol.Optional('name'): str,
    vol.Optional('user_id'): vol.Any(str, None),
    vol.Optional(CONF_DEVICE_TRACKERS, default=[]): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_update_person(hass: HomeAssistantType,
                           connection: websocket_api.ActiveConnection, msg):
    """Update a person."""
    manager = hass.data[DOMAIN]  # type: PersonManager
    changes = {}
    for key in ('name', 'user_id', 'device_trackers'):
        if key in msg:
            changes[key] = msg[key]

    person = await manager.async_update_person(msg['person_id'], **changes)
    connection.send_result(msg['id'], person)


@websocket_api.websocket_command({
    vol.Required('type'): 'person/delete',
    vol.Required('person_id'): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_delete_person(hass: HomeAssistantType,
                           connection: websocket_api.ActiveConnection,
                           msg):
    """Delete a person."""
    manager = hass.data[DOMAIN]  # type: PersonManager
    await manager.async_delete_person(msg['person_id'])
    connection.send_result(msg['id'])
