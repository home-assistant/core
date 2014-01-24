"""
homeassistant.components
~~~~~~~~~~~~~~~~~~~~~~~~

This package contains components that can be plugged into Home Assistant.

Component design guidelines:

Each component defines a constant DOMAIN that is equal to its filename.

Each component that tracks states should create state entity names in the
format "<DOMAIN>.<OBJECT_ID>".

Each component should publish services only under its own domain.

"""

import importlib

import homeassistant as ha
import homeassistant.util as util

ATTR_ENTITY_ID = 'entity_id'

STATE_ON = 'on'
STATE_OFF = 'off'
STATE_NOT_HOME = 'not_home'
STATE_HOME = 'home'

SERVICE_TURN_ON = 'turn_on'
SERVICE_TURN_OFF = 'turn_off'

_LOADED_MOD = {}


def _get_module(module):
    """ Helper function to load a module. """
    try:
        return _LOADED_MOD[module]

    except KeyError:
        # if module key did not exist in loaded dict
        try:
            module = _LOADED_MOD[module] = importlib.import_module(
                'homeassistant.components.'+module)

            return module

        except ImportError:
            # If module does not exist
            return None


def is_on(statemachine, entity_id=None):
    """ Loads up the module to call the is_on method.
    If there is no entity id given we will check all. """
    entity_ids = [entity_id] if entity_id else statemachine.entity_ids

    for entity_id in entity_ids:
        domain = util.split_entity_id(entity_id)[0]

        try:
            if _get_module(domain).is_on(statemachine, entity_id):
                return True

        except AttributeError:
            # method is_on does not exist within module
            pass

    return False


def turn_on(bus, entity_id=None):
    """ Turns specified entity on if possible. """
    # If there is no entity_id we do not know which domain to call.
    if not entity_id:
        return

    domain = util.split_entity_id(entity_id)[0]

    try:
        bus.call_service(domain, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id})
    except ha.ServiceDoesNotExistError:
        # turn_on service does not exist
        pass


def turn_off(bus, entity_id=None):
    """ Turns specified entity off. """
    # If there is no entity_id we do not know which domain to call.
    if not entity_id:
        return

    domain = util.split_entity_id(entity_id)[0]

    try:
        bus.call_service(domain, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id})
    except ha.ServiceDoesNotExistError:
        # turn_off service does not exist
        pass


def setup(bus):
    """ Setup general services related to homeassistant. """

    bus.register_service(ha.DOMAIN, SERVICE_TURN_OFF,
                         lambda service:
                         turn_off(bus, service.data.get(ATTR_ENTITY_ID)))

    bus.register_service(ha.DOMAIN, SERVICE_TURN_ON,
                         lambda service:
                         turn_on(bus, service.data.get(ATTR_ENTITY_ID)))

    return True
