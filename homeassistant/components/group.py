"""
Provide the functionality to group entities.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/group/
"""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant import config as conf_util, core as ha
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_ICON, CONF_NAME, STATE_CLOSED, STATE_HOME,
    STATE_NOT_HOME, STATE_OFF, STATE_ON, STATE_OPEN, STATE_LOCKED,
    STATE_UNLOCKED, STATE_OK, STATE_PROBLEM, STATE_UNKNOWN,
    ATTR_ASSUMED_STATE, SERVICE_RELOAD)
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv
from homeassistant.util.async import run_coroutine_threadsafe

DOMAIN = 'group'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_ENTITIES = 'entities'
CONF_VIEW = 'view'
CONF_CONTROL = 'control'

ATTR_ADD_ENTITIES = 'add_entities'
ATTR_AUTO = 'auto'
ATTR_CONTROL = 'control'
ATTR_ENTITIES = 'entities'
ATTR_ICON = 'icon'
ATTR_NAME = 'name'
ATTR_OBJECT_ID = 'object_id'
ATTR_ORDER = 'order'
ATTR_VIEW = 'view'
ATTR_VISIBLE = 'visible'

SERVICE_SET_VISIBILITY = 'set_visibility'
SERVICE_SET = 'set'
SERVICE_REMOVE = 'remove'

CONTROL_TYPES = vol.In(['hidden', None])

SET_VISIBILITY_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VISIBLE): cv.boolean
})

RELOAD_SERVICE_SCHEMA = vol.Schema({})

SET_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_OBJECT_ID): cv.slug,
    vol.Optional(ATTR_NAME): cv.string,
    vol.Optional(ATTR_VIEW): cv.boolean,
    vol.Optional(ATTR_ICON): cv.string,
    vol.Optional(ATTR_CONTROL): CONTROL_TYPES,
    vol.Optional(ATTR_VISIBLE): cv.boolean,
    vol.Exclusive(ATTR_ENTITIES, 'entities'): cv.entity_ids,
    vol.Exclusive(ATTR_ADD_ENTITIES, 'entities'): cv.entity_ids,
})

REMOVE_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_OBJECT_ID): cv.slug,
})

_LOGGER = logging.getLogger(__name__)


def _conf_preprocess(value):
    """Preprocess alternative configuration formats."""
    if not isinstance(value, dict):
        value = {CONF_ENTITIES: value}

    return value


GROUP_SCHEMA = vol.Schema({
    vol.Optional(CONF_ENTITIES): vol.Any(cv.entity_ids, None),
    CONF_VIEW: cv.boolean,
    CONF_NAME: cv.string,
    CONF_ICON: cv.icon,
    CONF_CONTROL: CONTROL_TYPES,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({cv.match_all: vol.All(_conf_preprocess, GROUP_SCHEMA)})
}, extra=vol.ALLOW_EXTRA)

# List of ON/OFF state tuples for groupable states
_GROUP_TYPES = [(STATE_ON, STATE_OFF), (STATE_HOME, STATE_NOT_HOME),
                (STATE_OPEN, STATE_CLOSED), (STATE_LOCKED, STATE_UNLOCKED),
                (STATE_PROBLEM, STATE_OK)]


def _get_group_on_off(state):
    """Determine the group on/off states based on a state."""
    for states in _GROUP_TYPES:
        if state in states:
            return states

    return None, None


def is_on(hass, entity_id):
    """Test if the group state is in its ON-state."""
    state = hass.states.get(entity_id)

    if state:
        group_on, _ = _get_group_on_off(state.state)

        # If we found a group_type, compare to ON-state
        return group_on is not None and state.state == group_on

    return False


def reload(hass):
    """Reload the automation from config."""
    hass.add_job(async_reload, hass)


@callback
def async_reload(hass):
    """Reload the automation from config."""
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_RELOAD))


def set_visibility(hass, entity_id=None, visible=True):
    """Hide or shows a group."""
    data = {ATTR_ENTITY_ID: entity_id, ATTR_VISIBLE: visible}
    hass.services.call(DOMAIN, SERVICE_SET_VISIBILITY, data)


def set_group(hass, object_id, name=None, entity_ids=None, visible=None,
              icon=None, view=None, control=None, add=None):
    """Create a new user group."""
    hass.add_job(
        async_set_group, hass, object_id, name, entity_ids, visible, icon,
        view, control, add)


@callback
def async_set_group(hass, object_id, name=None, entity_ids=None, visible=None,
                    icon=None, view=None, control=None, add=None):
    """Create a new user group."""
    data = {
        key: value for key, value in [
            (ATTR_OBJECT_ID, object_id),
            (ATTR_NAME, name),
            (ATTR_ENTITIES, entity_ids),
            (ATTR_VISIBLE, visible),
            (ATTR_ICON, icon),
            (ATTR_VIEW, view),
            (ATTR_CONTROL, control),
            (ATTR_ADD_ENTITIES, add),
        ] if value is not None
    }

    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_SET, data))


def remove(hass, name):
    """Remove a user group."""
    hass.add_job(async_remove, hass, name)


@callback
def async_remove(hass, object_id):
    """Remove a user group."""
    data = {ATTR_OBJECT_ID: object_id}
    hass.async_add_job(hass.services.async_call(DOMAIN, SERVICE_REMOVE, data))


def expand_entity_ids(hass, entity_ids):
    """Return entity_ids with group entity ids replaced by their members.

    Async friendly.
    """
    found_ids = []

    for entity_id in entity_ids:
        if not isinstance(entity_id, str):
            continue

        entity_id = entity_id.lower()

        try:
            # If entity_id points at a group, expand it
            domain, _ = ha.split_entity_id(entity_id)

            if domain == DOMAIN:
                found_ids.extend(
                    ent_id for ent_id
                    in expand_entity_ids(hass, get_entity_ids(hass, entity_id))
                    if ent_id not in found_ids)

            else:
                if entity_id not in found_ids:
                    found_ids.append(entity_id)

        except AttributeError:
            # Raised by split_entity_id if entity_id is not a string
            pass

    return found_ids


def get_entity_ids(hass, entity_id, domain_filter=None):
    """Get members of this group.

    Async friendly.
    """
    group = hass.states.get(entity_id)

    if not group or ATTR_ENTITY_ID not in group.attributes:
        return []

    entity_ids = group.attributes[ATTR_ENTITY_ID]

    if not domain_filter:
        return entity_ids

    domain_filter = domain_filter.lower() + '.'

    return [ent_id for ent_id in entity_ids
            if ent_id.startswith(domain_filter)]


@asyncio.coroutine
def async_setup(hass, config):
    """Set up all groups found definded in the configuration."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    service_groups = {}

    yield from _async_process_config(hass, config, component)

    descriptions = yield from hass.async_add_job(
        conf_util.load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml')
    )

    @asyncio.coroutine
    def reload_service_handler(service):
        """Remove all groups and load new ones from config."""
        conf = yield from component.async_prepare_reload()
        if conf is None:
            return
        yield from _async_process_config(hass, conf, component)

    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler,
        descriptions[DOMAIN][SERVICE_RELOAD], schema=RELOAD_SERVICE_SCHEMA)

    @asyncio.coroutine
    def groups_service_handler(service):
        """Handle dynamic group service functions."""
        object_id = service.data[ATTR_OBJECT_ID]

        # new group
        if service.service == SERVICE_SET and object_id not in service_groups:
            entity_ids = service.data.get(ATTR_ENTITIES) or \
                service.data.get(ATTR_ADD_ENTITIES) or None

            extra_arg = {attr: service.data[attr] for attr in (
                ATTR_VISIBLE, ATTR_ICON, ATTR_VIEW, ATTR_CONTROL
            ) if service.data.get(attr) is not None}

            new_group = yield from Group.async_create_group(
                hass, service.data.get(ATTR_NAME, object_id),
                object_id=object_id,
                entity_ids=entity_ids,
                user_defined=False,
                **extra_arg
            )

            service_groups[object_id] = new_group
            return

        # update group
        if service.service == SERVICE_SET:
            group = service_groups[object_id]
            need_update = False

            if ATTR_ADD_ENTITIES in service.data:
                delta = service.data[ATTR_ADD_ENTITIES]
                entity_ids = set(group.tracking) | set(delta)
                yield from group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_ENTITIES in service.data:
                entity_ids = service.data[ATTR_ENTITIES]
                yield from group.async_update_tracked_entity_ids(entity_ids)

            if ATTR_NAME in service.data:
                group.name = service.data[ATTR_NAME]
                need_update = True

            if ATTR_VISIBLE in service.data:
                group.visible = service.data[ATTR_VISIBLE]
                need_update = True

            if ATTR_ICON in service.data:
                group.icon = service.data[ATTR_ICON]
                need_update = True

            if ATTR_CONTROL in service.data:
                group.control = service.data[ATTR_CONTROL]
                need_update = True

            if ATTR_VIEW in service.data:
                group.view = service.data[ATTR_VIEW]
                need_update = True

            if need_update:
                yield from group.async_update_ha_state()

            return

        # remove group
        if service.service == SERVICE_REMOVE:
            if object_id not in service_groups:
                _LOGGER.warning("Group '%s' not exists!", object_id)
                return

            del_group = service_groups.pop(object_id)
            yield from del_group.async_stop()

    hass.services.async_register(
        DOMAIN, SERVICE_SET, groups_service_handler,
        descriptions[DOMAIN][SERVICE_SET], schema=SET_SERVICE_SCHEMA)

    hass.services.async_register(
        DOMAIN, SERVICE_REMOVE, groups_service_handler,
        descriptions[DOMAIN][SERVICE_REMOVE], schema=REMOVE_SERVICE_SCHEMA)

    @asyncio.coroutine
    def visibility_service_handler(service):
        """Change visibility of a group."""
        visible = service.data.get(ATTR_VISIBLE)

        tasks = []
        for group in component.async_extract_from_service(service,
                                                          expand_group=False):
            group.visible = visible
            tasks.append(group.async_update_ha_state())

        if tasks:
            yield from asyncio.wait(tasks, loop=hass.loop)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_VISIBILITY, visibility_service_handler,
        descriptions[DOMAIN][SERVICE_SET_VISIBILITY],
        schema=SET_VISIBILITY_SERVICE_SCHEMA)

    return True


@asyncio.coroutine
def _async_process_config(hass, config, component):
    """Process group configuration."""
    groups = []
    for object_id, conf in config.get(DOMAIN, {}).items():
        name = conf.get(CONF_NAME, object_id)
        entity_ids = conf.get(CONF_ENTITIES) or []
        icon = conf.get(CONF_ICON)
        view = conf.get(CONF_VIEW)
        control = conf.get(CONF_CONTROL)

        # Don't create tasks and await them all. The order is important as
        # groups get a number based on creation order.
        group = yield from Group.async_create_group(
            hass, name, entity_ids, icon=icon, view=view,
            control=control, object_id=object_id)
        groups.append(group)

    if groups:
        yield from component.async_add_entities(groups)


class Group(Entity):
    """Track a group of entity ids."""

    def __init__(self, hass, name, order=None, visible=True, icon=None,
                 view=False, control=None, user_defined=True):
        """Initialize a group.

        This Object has factory function for creation.
        """
        self.hass = hass
        self._name = name
        self._state = STATE_UNKNOWN
        self._icon = icon
        self.view = view
        self.tracking = []
        self.group_on = None
        self.group_off = None
        self.visible = visible
        self.control = control
        self._user_defined = user_defined
        self._order = order
        self._assumed_state = False
        self._async_unsub_state_changed = None

    @staticmethod
    def create_group(hass, name, entity_ids=None, user_defined=True,
                     visible=True, icon=None, view=False, control=None,
                     object_id=None):
        """Initialize a group."""
        return run_coroutine_threadsafe(
            Group.async_create_group(
                hass, name, entity_ids, user_defined, visible, icon, view,
                control, object_id),
            hass.loop).result()

    @staticmethod
    @asyncio.coroutine
    def async_create_group(hass, name, entity_ids=None, user_defined=True,
                           visible=True, icon=None, view=False, control=None,
                           object_id=None):
        """Initialize a group.

        This method must be run in the event loop.
        """
        group = Group(
            hass, name,
            order=len(hass.states.async_entity_ids(DOMAIN)),
            visible=visible, icon=icon, view=view, control=control,
            user_defined=user_defined
        )

        group.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, object_id or name, hass=hass)

        # run other async stuff
        if entity_ids is not None:
            yield from group.async_update_tracked_entity_ids(entity_ids)
        else:
            yield from group.async_update_ha_state(True)

        return group

    @property
    def should_poll(self):
        """No need to poll because groups will update themselves."""
        return False

    @property
    def name(self):
        """Return the name of the group."""
        return self._name

    @name.setter
    def name(self, value):
        """Set Group name."""
        self._name = value

    @property
    def state(self):
        """Return the state of the group."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the group."""
        return self._icon

    @icon.setter
    def icon(self, value):
        """Set Icon for group."""
        self._icon = value

    @property
    def hidden(self):
        """If group should be hidden or not."""
        if self.visible and not self.view:
            return False
        return True

    @property
    def state_attributes(self):
        """Return the state attributes for the group."""
        data = {
            ATTR_ENTITY_ID: self.tracking,
            ATTR_ORDER: self._order,
        }
        if not self._user_defined:
            data[ATTR_AUTO] = True
        if self.view:
            data[ATTR_VIEW] = True
        if self.control:
            data[ATTR_CONTROL] = self.control
        return data

    @property
    def assumed_state(self):
        """Test if any member has an assumed state."""
        return self._assumed_state

    def update_tracked_entity_ids(self, entity_ids):
        """Update the member entity IDs."""
        run_coroutine_threadsafe(
            self.async_update_tracked_entity_ids(entity_ids), self.hass.loop
        ).result()

    @asyncio.coroutine
    def async_update_tracked_entity_ids(self, entity_ids):
        """Update the member entity IDs.

        This method must be run in the event loop.
        """
        yield from self.async_stop()
        self.tracking = tuple(ent_id.lower() for ent_id in entity_ids)
        self.group_on, self.group_off = None, None

        yield from self.async_update_ha_state(True)
        self.async_start()

    def start(self):
        """Start tracking members."""
        self.hass.add_job(self.async_start)

    @callback
    def async_start(self):
        """Start tracking members.

        This method must be run in the event loop.
        """
        if self._async_unsub_state_changed is None:
            self._async_unsub_state_changed = async_track_state_change(
                self.hass, self.tracking, self._async_state_changed_listener
            )

    def stop(self):
        """Unregister the group from Home Assistant."""
        run_coroutine_threadsafe(self.async_stop(), self.hass.loop).result()

    @asyncio.coroutine
    def async_stop(self):
        """Unregister the group from Home Assistant.

        This method must be run in the event loop.
        """
        yield from self.async_remove()

    @asyncio.coroutine
    def async_update(self):
        """Query all members and determine current group state."""
        self._state = STATE_UNKNOWN
        self._async_update_group_state()

    def async_remove(self):
        """Remove group from HASS.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._async_unsub_state_changed:
            self._async_unsub_state_changed()
            self._async_unsub_state_changed = None

        return super().async_remove()

    @asyncio.coroutine
    def _async_state_changed_listener(self, entity_id, old_state, new_state):
        """Respond to a member state changing.

        This method must be run in the event loop.
        """
        # removed
        if self._async_unsub_state_changed is None:
            return

        self._async_update_group_state(new_state)
        yield from self.async_update_ha_state()

    @property
    def _tracking_states(self):
        """Return the states that the group is tracking."""
        states = []

        for entity_id in self.tracking:
            state = self.hass.states.get(entity_id)

            if state is not None:
                states.append(state)

        return states

    @callback
    def _async_update_group_state(self, tr_state=None):
        """Update group state.

        Optionally you can provide the only state changed since last update
        allowing this method to take shortcuts.

        This method must be run in the event loop.
        """
        # To store current states of group entities. Might not be needed.
        states = None
        gr_state = self._state
        gr_on = self.group_on
        gr_off = self.group_off

        # We have not determined type of group yet
        if gr_on is None:
            if tr_state is None:
                states = self._tracking_states

                for state in states:
                    gr_on, gr_off = \
                        _get_group_on_off(state.state)
                    if gr_on is not None:
                        break
            else:
                gr_on, gr_off = _get_group_on_off(tr_state.state)

            if gr_on is not None:
                self.group_on, self.group_off = gr_on, gr_off

        # We cannot determine state of the group
        if gr_on is None:
            return

        if tr_state is None or ((gr_state == gr_on and
                                 tr_state.state == gr_off) or
                                tr_state.state not in (gr_on, gr_off)):
            if states is None:
                states = self._tracking_states

            if any(state.state == gr_on for state in states):
                self._state = gr_on
            else:
                self._state = gr_off

        elif tr_state.state in (gr_on, gr_off):
            self._state = tr_state.state

        if tr_state is None or self._assumed_state and \
           not tr_state.attributes.get(ATTR_ASSUMED_STATE):
            if states is None:
                states = self._tracking_states

            self._assumed_state = any(
                state.attributes.get(ATTR_ASSUMED_STATE) for state
                in states)

        elif tr_state.attributes.get(ATTR_ASSUMED_STATE):
            self._assumed_state = True
