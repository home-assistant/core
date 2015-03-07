"""
homeassistant.components.groups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to group devices that can be turned on or off.
"""

import homeassistant as ha
from homeassistant.helpers import generate_entity_id
import homeassistant.util as util
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, STATE_ON, STATE_OFF,
    STATE_HOME, STATE_NOT_HOME, STATE_UNKNOWN)

DOMAIN = "group"
DEPENDENCIES = []

ENTITY_ID_FORMAT = DOMAIN + ".{}"

ATTR_AUTO = "auto"

# List of ON/OFF state tuples for groupable states
_GROUP_TYPES = [(STATE_ON, STATE_OFF), (STATE_HOME, STATE_NOT_HOME)]


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
            domain, _ = util.split_entity_id(entity_id)

            if domain == DOMAIN:
                found_ids.extend(
                    ent_id for ent_id
                    in get_entity_ids(hass, entity_id)
                    if ent_id not in found_ids)

            else:
                if entity_id not in found_ids:
                    found_ids.append(entity_id)

        except AttributeError:
            # Raised by util.split_entity_id if entity_id is not a string
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
    for name, entity_ids in config.get(DOMAIN, {}).items():
        # Support old deprecated method - 2/28/2015
        if isinstance(entity_ids, str):
            entity_ids = entity_ids.split(",")

        setup_group(hass, name, entity_ids)

    return True


class Group(object):
    """ Tracks a group of entity ids. """
    def __init__(self, hass, name, entity_ids=None, user_defined=True):
        self.hass = hass
        self.name = name
        self.user_defined = user_defined

        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT, name, hass=hass)

        self.tracking = []
        self.group_on, self.group_off = None, None

        if entity_ids is not None:
            self.update_tracked_entity_ids(entity_ids)
        else:
            self.force_update()

    @property
    def state(self):
        """ Return the current state from the group. """
        return self.hass.states.get(self.entity_id)

    @property
    def state_attr(self):
        """ State attributes of this group. """
        return {
            ATTR_ENTITY_ID: self.tracking,
            ATTR_AUTO: not self.user_defined,
            ATTR_FRIENDLY_NAME: self.name
        }

    def update_tracked_entity_ids(self, entity_ids):
        """ Update the tracked entity IDs. """
        self.stop()
        self.tracking = tuple(ent_id.lower() for ent_id in entity_ids)
        self.group_on, self.group_off = None, None

        self.force_update()

        self.start()

    def force_update(self):
        """ Query all the tracked states and update group state. """
        for entity_id in self.tracking:
            state = self.hass.states.get(entity_id)

            if state is not None:
                self._update_group_state(state.entity_id, None, state)

        # If parsing the entitys did not result in a state, set UNKNOWN
        if self.state is None:
            self.hass.states.set(
                self.entity_id, STATE_UNKNOWN, self.state_attr)

    def start(self):
        """ Starts the tracking. """
        self.hass.states.track_change(self.tracking, self._update_group_state)

    def stop(self):
        """ Unregisters the group from Home Assistant. """
        self.hass.states.remove(self.entity_id)

        self.hass.bus.remove_listener(
            ha.EVENT_STATE_CHANGED, self._update_group_state)

    def _update_group_state(self, entity_id, old_state, new_state):
        """ Updates the group state based on a state change by
            a tracked entity. """

        # We have not determined type of group yet
        if self.group_on is None:
            self.group_on, self.group_off = _get_group_on_off(new_state.state)

            if self.group_on is not None:
                # New state of the group is going to be based on the first
                # state that we can recognize
                self.hass.states.set(
                    self.entity_id, new_state.state, self.state_attr)

            return

        # There is already a group state
        cur_gr_state = self.hass.states.get(self.entity_id).state
        group_on, group_off = self.group_on, self.group_off

        # if cur_gr_state = OFF and new_state = ON: set ON
        # if cur_gr_state = ON and new_state = OFF: research
        # else: ignore

        if cur_gr_state == group_off and new_state.state == group_on:

            self.hass.states.set(
                self.entity_id, group_on, self.state_attr)

        elif (cur_gr_state == group_on and
              new_state.state == group_off):

            # Check if any of the other states is still on
            if not any(self.hass.states.is_state(ent_id, group_on)
                       for ent_id in self.tracking if entity_id != ent_id):
                self.hass.states.set(
                    self.entity_id, group_off, self.state_attr)


def setup_group(hass, name, entity_ids, user_defined=True):
    """ Sets up a group state that is the combined state of
        several states. Supports ON/OFF and DEVICE_HOME/DEVICE_NOT_HOME. """

    return Group(hass, name, entity_ids, user_defined)
