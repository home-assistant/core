"""Support for tracking people."""
from collections import OrderedDict
from itertools import chain
import logging
from typing import Optional
import uuid

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN, ATTR_SOURCE_TYPE, SOURCE_TYPE_GPS)
from homeassistant.const import (
    ATTR_ID, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_GPS_ACCURACY,
    CONF_ID, CONF_NAME, EVENT_HOMEASSISTANT_START,
    STATE_UNKNOWN, STATE_UNAVAILABLE, STATE_HOME, STATE_NOT_HOME)
from homeassistant.core import callback, Event, State
from homeassistant.auth import EVENT_USER_REMOVED
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

ATTR_EDITABLE = 'editable'
ATTR_SOURCE = 'source'
ATTR_USER_ID = 'user_id'

CONF_DEVICE_TRACKERS = 'device_trackers'
CONF_USER_ID = 'user_id'

DOMAIN = 'person'

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
SAVE_DELAY = 10
# Device tracker states to ignore
IGNORE_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE)

PERSON_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_USER_ID): cv.string,
    vol.Optional(CONF_DEVICE_TRACKERS, default=[]): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)),
})

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.All(
        cv.ensure_list, cv.remove_falsy, [PERSON_SCHEMA])
}, extra=vol.ALLOW_EXTRA)

_UNDEF = object()


@bind_hass
async def async_create_person(hass, name, *, user_id=None,
                              device_trackers=None):
    """Create a new person."""
    await hass.data[DOMAIN].async_create_person(
        name=name,
        user_id=user_id,
        device_trackers=device_trackers,
    )


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
                _LOGGER.error(
                    "Found config user with duplicate ID: %s", person_id)
                continue

            config_data[person_id] = conf

    @property
    def storage_persons(self):
        """Iterate over persons stored in storage."""
        return list(self.storage_data.values())

    @property
    def config_persons(self):
        """Iterate over persons stored in config."""
        return list(self.config_data.values())

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
        seen_users = set()

        for person_conf in self.config_data.values():
            person_id = person_conf[CONF_ID]
            user_id = person_conf.get(CONF_USER_ID)

            if user_id is not None:
                if await self.hass.auth.async_get_user(user_id) is None:
                    _LOGGER.error(
                        "Invalid user_id detected for person %s", person_id)
                    continue

                if user_id in seen_users:
                    _LOGGER.error(
                        "Duplicate user_id %s detected for person %s",
                        user_id, person_id)
                    continue

                seen_users.add(user_id)

            entities.append(Person(person_conf, False))

        # To make sure IDs don't overlap between config/storage
        seen_persons = set(self.config_data)

        for person_conf in storage_data.values():
            person_id = person_conf[CONF_ID]
            user_id = person_conf[CONF_USER_ID]

            if person_id in seen_persons:
                _LOGGER.error(
                    "Skipping adding person from storage with same ID as"
                    " configuration.yaml entry: %s", person_id)
                continue

            if user_id is not None and user_id in seen_users:
                _LOGGER.error(
                    "Duplicate user_id %s detected for person %s",
                    user_id, person_id)
                continue

            # To make sure all users have just 1 person linked.
            seen_users.add(user_id)

            entities.append(Person(person_conf, True))

        if entities:
            await self.component.async_add_entities(entities)

        self.hass.bus.async_listen(EVENT_USER_REMOVED, self._user_removed)

    async def async_create_person(
            self, *, name, device_trackers=None, user_id=None):
        """Create a new person."""
        if not name:
            raise ValueError("Name is required")

        if user_id is not None:
            await self._validate_user_id(user_id)

        person = {
            CONF_ID: uuid.uuid4().hex,
            CONF_NAME: name,
            CONF_USER_ID: user_id,
            CONF_DEVICE_TRACKERS: device_trackers or [],
        }
        self.storage_data[person[CONF_ID]] = person
        self._async_schedule_save()
        await self.component.async_add_entities([Person(person, True)])
        return person

    async def async_update_person(self, person_id, *, name=_UNDEF,
                                  device_trackers=_UNDEF, user_id=_UNDEF):
        """Update person."""
        current = self.storage_data.get(person_id)

        if current is None:
            raise ValueError("Invalid person specified.")

        changes = {
            key: value for key, value in (
                (CONF_NAME, name),
                (CONF_DEVICE_TRACKERS, device_trackers),
                (CONF_USER_ID, user_id)
            ) if value is not _UNDEF and current[key] != value
        }

        if CONF_USER_ID in changes and user_id is not None:
            await self._validate_user_id(user_id)

        self.storage_data[person_id].update(changes)
        self._async_schedule_save()

        for entity in self.component.entities:
            if entity.unique_id == person_id:
                entity.person_updated()
                break

        return self.storage_data[person_id]

    async def async_delete_person(self, person_id):
        """Delete person."""
        if person_id not in self.storage_data:
            raise ValueError("Invalid person specified.")

        self.storage_data.pop(person_id)
        self._async_schedule_save()
        ent_reg = await self.hass.helpers.entity_registry.async_get_registry()

        for entity in self.component.entities:
            if entity.unique_id == person_id:
                await entity.async_remove()
                ent_reg.async_remove(entity.entity_id)
                break

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

    async def _validate_user_id(self, user_id):
        """Validate the used user_id."""
        if await self.hass.auth.async_get_user(user_id) is None:
            raise ValueError("User does not exist")

        if any(person for person
               in chain(self.storage_data.values(),
                        self.config_data.values())
               if person.get(CONF_USER_ID) == user_id):
            raise ValueError("User already taken")

    async def _user_removed(self, event: Event):
        """Handle event that a person is removed."""
        user_id = event.data['user_id']
        for person in self.storage_data.values():
            if person[CONF_USER_ID] == user_id:
                await self.async_update_person(
                    person_id=person[CONF_ID],
                    user_id=None
                )


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
        self._editable = editable
        self._latitude = None
        self._longitude = None
        self._gps_accuracy = None
        self._source = None
        self._state = None
        self._unsub_track_device = None

    @property
    def name(self):
        """Return the name of the entity."""
        return self._config[CONF_NAME]

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
        data = {
            ATTR_EDITABLE: self._editable,
            ATTR_ID: self.unique_id,
        }
        if self._latitude is not None:
            data[ATTR_LATITUDE] = self._latitude
        if self._longitude is not None:
            data[ATTR_LONGITUDE] = self._longitude
        if self._gps_accuracy is not None:
            data[ATTR_GPS_ACCURACY] = self._gps_accuracy
        if self._source is not None:
            data[ATTR_SOURCE] = self._source
        user_id = self._config.get(CONF_USER_ID)
        if user_id is not None:
            data[ATTR_USER_ID] = user_id
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

        if self.hass.is_running:
            # Update person now if hass is already running.
            self.person_updated()
        else:
            # Wait for hass start to not have race between person
            # and device trackers finishing setup.
            @callback
            def person_start_hass(now):
                self.person_updated()

            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, person_start_hass)

    @callback
    def person_updated(self):
        """Handle when the config is updated."""
        if self._unsub_track_device is not None:
            self._unsub_track_device()
            self._unsub_track_device = None

        trackers = self._config.get(CONF_DEVICE_TRACKERS)

        if trackers:
            _LOGGER.debug(
                "Subscribe to device trackers for %s", self.entity_id)

            self._unsub_track_device = async_track_state_change(
                self.hass, trackers, self._async_handle_tracker_update)

        self._update_state()

    @callback
    def _async_handle_tracker_update(self, entity, old_state, new_state):
        """Handle the device tracker state changes."""
        self._update_state()

    @callback
    def _update_state(self):
        """Update the state."""
        latest_non_gps_home = latest_not_home = latest_gps = latest = None
        for entity_id in self._config.get(CONF_DEVICE_TRACKERS, []):
            state = self.hass.states.get(entity_id)

            if not state or state.state in IGNORE_STATES:
                continue

            if state.attributes.get(ATTR_SOURCE_TYPE) == SOURCE_TYPE_GPS:
                latest_gps = _get_latest(latest_gps, state)
            elif state.state == STATE_HOME:
                latest_non_gps_home = _get_latest(latest_non_gps_home, state)
            elif state.state == STATE_NOT_HOME:
                latest_not_home = _get_latest(latest_not_home, state)

        if latest_non_gps_home:
            latest = latest_non_gps_home
        elif latest_gps:
            latest = latest_gps
        else:
            latest = latest_not_home

        if latest:
            self._parse_source_state(latest)
        else:
            self._state = None
            self._source = None
            self._latitude = None
            self._longitude = None
            self._gps_accuracy = None

        self.async_schedule_update_ha_state()

    @callback
    def _parse_source_state(self, state):
        """Parse source state and set person attributes.

        This is a device tracker state or the restored person state.
        """
        self._state = state.state
        self._source = state.entity_id
        self._latitude = state.attributes.get(ATTR_LATITUDE)
        self._longitude = state.attributes.get(ATTR_LONGITUDE)
        self._gps_accuracy = state.attributes.get(ATTR_GPS_ACCURACY)


@websocket_api.websocket_command({
    vol.Required('type'): 'person/list',
})
def ws_list_person(hass: HomeAssistantType,
                   connection: websocket_api.ActiveConnection, msg):
    """List persons."""
    manager = hass.data[DOMAIN]  # type: PersonManager
    connection.send_result(msg['id'], {
        'storage': manager.storage_persons,
        'config': manager.config_persons,
    })


@websocket_api.websocket_command({
    vol.Required('type'): 'person/create',
    vol.Required('name'): vol.All(str, vol.Length(min=1)),
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
    try:
        person = await manager.async_create_person(
            name=msg['name'],
            user_id=msg.get('user_id'),
            device_trackers=msg['device_trackers']
        )
        connection.send_result(msg['id'], person)
    except ValueError as err:
        connection.send_error(
            msg['id'], websocket_api.const.ERR_INVALID_FORMAT, str(err))


@websocket_api.websocket_command({
    vol.Required('type'): 'person/update',
    vol.Required('person_id'): str,
    vol.Required('name'): vol.All(str, vol.Length(min=1)),
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

    try:
        person = await manager.async_update_person(msg['person_id'], **changes)
        connection.send_result(msg['id'], person)
    except ValueError as err:
        connection.send_error(
            msg['id'], websocket_api.const.ERR_INVALID_FORMAT, str(err))


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


def _get_latest(prev: Optional[State], curr: State):
    """Get latest state."""
    if prev is None or curr.last_updated > prev.last_updated:
        return curr
    return prev
