"""
homeassistant.components.groups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to group devices that can be turned on or off.
"""

import logging

import homeassistant as ha
import homeassistant.util as util
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, STATE_HOME, STATE_NOT_HOME)

DOMAIN = "group"
DEPENDENCIES = []

ENTITY_ID_FORMAT = DOMAIN + ".{}"

ATTR_AUTO = "auto"

# List of ON/OFF state tuples for groupable states
_GROUP_TYPES = [(STATE_ON, STATE_OFF), (STATE_HOME, STATE_NOT_HOME)]

_GROUPS = {}


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
    try:
        entity_ids = hass.states.get(entity_id).attributes[ATTR_ENTITY_ID]

        if domain_filter:
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
        entity_ids = entity_ids.split(",")

        setup_group(hass, name, entity_ids)

    return True


def setup_group(hass, name, entity_ids, user_defined=True):
    """ Sets up a group state that is the combined state of
        several states. Supports ON/OFF and DEVICE_HOME/DEVICE_NOT_HOME. """
    logger = logging.getLogger(__name__)

    # In case an iterable is passed in
    entity_ids = list(entity_ids)

    if not entity_ids:
        logger.error(
            'Error setting up group %s: no entities passed in to track', name)

        return False

    # Loop over the given entities to:
    #  - determine which group type this is (on_off, device_home)
    #  - determine which states exist and have groupable states
    #  - determine the current state of the group
    warnings = []
    group_ids = []
    group_on, group_off = None, None
    group_state = False

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)

        # Try to determine group type if we didn't yet
        if group_on is None and state:
            group_on, group_off = _get_group_on_off(state.state)

            if group_on is None:
                # We did not find a matching group_type
                warnings.append(
                    "Entity {} has ungroupable state '{}'".format(
                        name, state.state))

                continue

        # Check if entity exists
        if not state:
            warnings.append("Entity {} does not exist".format(entity_id))

        # Check if entity is invalid state
        elif state.state != group_off and state.state != group_on:

            warnings.append("State of {} is {} (expected: {} or {})".format(
                entity_id, state.state, group_off, group_on))

        # We have a valid group state
        else:
            group_ids.append(entity_id)

            # Keep track of the group state to init later on
            group_state = group_state or state.state == group_on

    # If none of the entities could be found during setup
    if not group_ids:
        logger.error('Unable to find any entities to track for group %s', name)

        return False

    elif warnings:
        logger.warning(
            'Warnings during setting up group %s: %s',
            name, ", ".join(warnings))

    group_entity_id = ENTITY_ID_FORMAT.format(util.slugify(name))
    state = group_on if group_state else group_off
    state_attr = {ATTR_ENTITY_ID: entity_ids, ATTR_AUTO: not user_defined}

    # pylint: disable=unused-argument
    def update_group_state(entity_id, old_state, new_state):
        """ Updates the group state based on a state change by
            a tracked entity. """

        cur_gr_state = hass.states.get(group_entity_id).state

        # if cur_gr_state = OFF and new_state = ON: set ON
        # if cur_gr_state = ON and new_state = OFF: research
        # else: ignore

        if cur_gr_state == group_off and new_state.state == group_on:

            hass.states.set(group_entity_id, group_on, state_attr)

        elif cur_gr_state == group_on and new_state.state == group_off:

            # Check if any of the other states is still on
            if not any([hass.states.is_state(ent_id, group_on)
                        for ent_id in group_ids
                        if entity_id != ent_id]):
                hass.states.set(group_entity_id, group_off, state_attr)

    _GROUPS[group_entity_id] = hass.states.track_change(
        group_ids, update_group_state)

    hass.states.set(group_entity_id, state, state_attr)

    return True


def remove_group(hass, name):
    """ Remove a group and its state listener from Home Assistant. """
    group_entity_id = ENTITY_ID_FORMAT.format(util.slugify(name))

    if hass.states.get(group_entity_id) is not None:
        hass.states.remove(group_entity_id)

    if group_entity_id in _GROUPS:
        hass.bus.remove_listener(
            ha.EVENT_STATE_CHANGED, _GROUPS.pop(group_entity_id))
