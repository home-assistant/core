"""
homeassistant.components.groups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to group devices that can be turned on or off.
"""

import logging

import homeassistant.util as util
from homeassistant.components import (STATE_ON, STATE_OFF,
                                      STATE_HOME, STATE_NOT_HOME,
                                      ATTR_ENTITY_ID)

DOMAIN = "group"
DEPENDENCIES = []

ENTITY_ID_FORMAT = DOMAIN + ".{}"

ATTR_AUTO = "auto"

_GROUP_TYPES = {
    "on_off": (STATE_ON, STATE_OFF),
    "home_not_home": (STATE_HOME, STATE_NOT_HOME)
}


def _get_group_type(state):
    """ Determine the group type based on the given group type. """
    for group_type, states in _GROUP_TYPES.items():
        if state in states:
            return group_type

    return None


def is_on(hass, entity_id):
    """ Returns if the group state is in its ON-state. """
    state = hass.states.get(entity_id)

    if state:
        group_type = _get_group_type(state.state)

        # If we found a group_type, compare to ON-state
        return group_type and state.state == _GROUP_TYPES[group_type][0]

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
            return [entity_id for entity_id in entity_ids
                    if entity_id.startswith(domain_filter)]
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


# pylint: disable=too-many-branches
def setup_group(hass, name, entity_ids, user_defined=True):
    """ Sets up a group state that is the combined state of
        several states. Supports ON/OFF and DEVICE_HOME/DEVICE_NOT_HOME. """

    # In case an iterable is passed in
    entity_ids = list(entity_ids)

    # Loop over the given entities to:
    #  - determine which group type this is (on_off, device_home)
    #  - if all states exist and have valid states
    #  - retrieve the current state of the group
    errors = []
    group_type, group_on, group_off, group_state = None, None, None, None

    for entity_id in entity_ids:
        state = hass.states.get(entity_id)

        # Try to determine group type if we didn't yet
        if not group_type and state:
            group_type = _get_group_type(state.state)

            if group_type:
                group_on, group_off = _GROUP_TYPES[group_type]
                group_state = group_off

            else:
                # We did not find a matching group_type
                errors.append(
                    "Entity {} has ungroupable state '{}'".format(
                        name, state.state))

                # Stop check all other entity IDs and report as error
                break

        # Check if entity exists
        if not state:
            errors.append("Entity {} does not exist".format(entity_id))

        # Check if entity is valid state
        elif state.state != group_off and state.state != group_on:

            errors.append("State of {} is {} (expected: {} or {})".format(
                entity_id, state.state, group_off, group_on))

        # Keep track of the group state to init later on
        elif state.state == group_on:
            group_state = group_on

    if group_type is None and not errors:
        errors.append('Unable to determine group type for {}'.format(name))

    if errors:
        logging.getLogger(__name__).error(
            "Error setting up group %s: %s", name, ", ".join(errors))

        return False

    else:
        group_entity_id = ENTITY_ID_FORMAT.format(name)
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
                            for ent_id in entity_ids
                            if entity_id != ent_id]):
                    hass.states.set(group_entity_id, group_off, state_attr)

        hass.track_state_change(entity_ids, update_group_state)

        hass.states.set(group_entity_id, group_state, state_attr)

        return True
