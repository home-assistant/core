"""
homeassistant.components.group
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides functionality to group devices that can be turned on or off.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/group/
"""
import logging
import json

import homeassistant.core as ha
from homeassistant.util import template
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.entity import (
    Entity, split_entity_id, generate_entity_id)
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF,
    STATE_HOME, STATE_NOT_HOME, STATE_OPEN, STATE_CLOSED,
    STATE_UNKNOWN, CONF_NAME, CONF_ICON)

DOMAIN = 'group'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_ENTITIES = 'entities'
CONF_VIEW = 'view'
CONF_STATE_TEMPLATE = 'state_template'
CONF_ATTR_TEMPLATE = 'attr_template'

ATTR_AUTO = 'auto'
ATTR_ORDER = 'order'
ATTR_VIEW = 'view'

# List of ON/OFF state tuples for groupable states
_GROUP_TYPES = [(STATE_ON, STATE_OFF), (STATE_HOME, STATE_NOT_HOME),
                (STATE_OPEN, STATE_CLOSED)]

_LOGGER = logging.getLogger(__name__)


def _get_group_on_off(state):
    """ Determine the group on/off states based on a state. """
    for states in _GROUP_TYPES:
        if state in states:
            return states

    return None, None


def is_on(hass, entity_id):
    """ Returns if the group state is in its ON-state. """
    state = hass.states.get(entity_id)

    if state:
        group_on, _ = _get_group_on_off(state.state)

        # If we found a group_type, compare to ON-state
        return group_on is not None and state.state == group_on

    return False


def expand_entity_ids(hass, entity_ids):
    """ Returns the given list of entity ids and expands group ids into
        the entity ids it represents if found. """
    found_ids = []

    for entity_id in entity_ids:
        if not isinstance(entity_id, str):
            continue

        entity_id = entity_id.lower()

        try:
            # If entity_id points at a group, expand it
            domain, _ = split_entity_id(entity_id)

            if domain == DOMAIN:
                found_ids.extend(
                    ent_id for ent_id
                    in get_entity_ids(hass, entity_id)
                    if ent_id not in found_ids)

            else:
                if entity_id not in found_ids:
                    found_ids.append(entity_id)

        except AttributeError:
            # Raised by split_entity_id if entity_id is not a string
            pass

    return found_ids


def get_entity_ids(hass, entity_id, domain_filter=None):
    """ Get the entity ids that make up this group. """
    entity_id = entity_id.lower()

    try:
        entity_ids = hass.states.get(entity_id).attributes[ATTR_ENTITY_ID]

        if domain_filter:
            domain_filter = domain_filter.lower()

            return [ent_id for ent_id in entity_ids
                    if ent_id.startswith(domain_filter)]
        else:
            return entity_ids

    except (AttributeError, KeyError):
        # AttributeError if state did not exist
        # KeyError if key did not exist in attributes
        return []


def setup(hass, config):
    """ Sets up all groups found definded in the configuration. """
    for object_id, conf in config.get(DOMAIN, {}).items():
        if not isinstance(conf, dict):
            conf = {CONF_ENTITIES: conf}

        name = conf.get(CONF_NAME, object_id)
        entity_ids = conf.get(CONF_ENTITIES)
        icon = conf.get(CONF_ICON)
        view = conf.get(CONF_VIEW)
        state_template = conf.get(CONF_STATE_TEMPLATE)
        attr_template = conf.get(CONF_ATTR_TEMPLATE)

        if isinstance(entity_ids, str):
            entity_ids = [ent.strip() for ent in entity_ids.split(",")]

        Group(hass, name, entity_ids, icon=icon, view=view,
              object_id=object_id, state_template=state_template,
              attr_template=attr_template)

    return True


class Group(Entity):
    """ Tracks a group of entity ids. """

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    def __init__(self, hass, name, entity_ids=None, user_defined=True,
                 icon=None, view=False, object_id=None, state_template=None,
                 attr_template=None):
        self.hass = hass
        self._name = name
        self._state = STATE_UNKNOWN
        self._order = len(hass.states.entity_ids(DOMAIN))
        self._user_defined = user_defined
        self._icon = icon
        self._view = view
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, object_id or name, hass=hass)
        self.tracking = []
        self.group_on = None
        self.group_off = None

        self._attr = {}
        self._attr_template = attr_template
        self._state_template = state_template

        if entity_ids is not None:
            self.update_tracked_entity_ids(entity_ids)
        else:
            self.update_ha_state(True)

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return self._icon

    @property
    def hidden(self):
        return not self._user_defined or self._view

    @property
    def state_attributes(self):
        data = {
            ATTR_ENTITY_ID: self.tracking,
            ATTR_ORDER: self._order,
        }
        if not self._user_defined:
            data[ATTR_AUTO] = True
        if self._view:
            data[ATTR_VIEW] = True

        data.update(self._attr)

        return data

    def update_tracked_entity_ids(self, entity_ids):
        """ Update the tracked entity IDs. """
        self.stop()
        self.tracking = tuple(ent_id.lower() for ent_id in entity_ids)
        self.group_on, self.group_off = None, None

        self.update_ha_state(True)

        self.start()

    def start(self):
        """ Starts the tracking. """
        track_state_change(
            self.hass, self.tracking, self._state_changed_listener)

    def stop(self):
        """ Unregisters the group from Home Assistant. """
        self.hass.states.remove(self.entity_id)

        self.hass.bus.remove_listener(
            ha.EVENT_STATE_CHANGED, self._state_changed_listener)

    def update(self):
        """ Query all the tracked states and determine current group state. """
        self._state = STATE_UNKNOWN

        for entity_id in self.tracking:
            state = self.hass.states.get(entity_id)

            if state is not None:
                self._state_changed_listener(entity_id, None, state)

    def _state_changed_listener(self, entity_id, old_state, new_state):
        """ Listener to receive state changes of tracked entities. """
        if self._state_template is None:
            self._process_tracked_state(new_state)
        else:
            self._process_tracked_state_template(entity_id, old_state,
                                                 new_state)
        if self._attr_template:
            self._process_tracked_attr_template(entity_id, old_state,
                                                new_state)
        self.update_ha_state()

    def _process_tracked_state_template(self, entity_id, old_state,
                                        new_state):
        """ Use template to process state from state changes """
        try:
            state = json.loads(template.render(self.hass,
                                               self._state_template,
                                               {"json": json,
                                                "entity_id": entity_id,
                                                "state": self._state,
                                                "from_state": old_state,
                                                "to_state": new_state}))

        except ValueError:
            _LOGGER.exception("State template must output valid json as state")
            return
        self._state = state

    def _process_tracked_attr_template(self, entity_id, old_state,
                                       new_state):
        """ Use template to process attr from state changes """
        def merge_dicts(dict1, dict2):
            """ Merge two dicts, not possible in jinja2 """
            tmp = dict1.copy()
            tmp.update(dict2)
            return tmp

        try:
            attr = json.loads(template.render(self.hass,
                                              self._attr_template,
                                              {"json": json,
                                               "merge_dicts": merge_dicts,
                                               "entity_id": entity_id,
                                               "old_attr": self._attr,
                                               "from_state": old_state,
                                               "to_state": new_state}))
        except ValueError:
            _LOGGER.exception("Attr template must output valid json as dict")
            return

        if not isinstance(attr, dict):
            _LOGGER.error("Attr template must return a attr dict as "
                          "json, got %s", attr)
            return
        self._attr = attr

    def _process_tracked_state(self, tr_state):
        """ Updates group state based on a new state of a tracked entity. """

        # We have not determined type of group yet
        if self.group_on is None:
            self.group_on, self.group_off = _get_group_on_off(tr_state.state)

            if self.group_on is not None:
                # New state of the group is going to be based on the first
                # state that we can recognize
                self._state = tr_state.state

            return

        # There is already a group state
        cur_gr_state = self._state
        group_on, group_off = self.group_on, self.group_off

        # if cur_gr_state = OFF and tr_state = ON: set ON
        # if cur_gr_state = ON and tr_state = OFF: research
        # else: ignore

        if cur_gr_state == group_off and tr_state.state == group_on:
            self._state = group_on

        elif cur_gr_state == group_on and tr_state.state == group_off:

            # Set to off if no other states are on
            if not any(self.hass.states.is_state(ent_id, group_on)
                       for ent_id in self.tracking
                       if tr_state.entity_id != ent_id):
                self._state = group_off
