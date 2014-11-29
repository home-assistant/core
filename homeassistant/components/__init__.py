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
import itertools as it
import logging

import homeassistant as ha
import homeassistant.util as util
from homeassistant.loader import get_component

# Contains one string or a list of strings, each being an entity id
ATTR_ENTITY_ID = 'entity_id'

# String with a friendly name for the entity
ATTR_FRIENDLY_NAME = "friendly_name"

# A picture to represent entity
ATTR_ENTITY_PICTURE = "entity_picture"

# The unit of measurement if applicable
ATTR_UNIT_OF_MEASUREMENT = "unit_of_measurement"

STATE_ON = 'on'
STATE_OFF = 'off'
STATE_HOME = 'home'
STATE_NOT_HOME = 'not_home'

SERVICE_TURN_ON = 'turn_on'
SERVICE_TURN_OFF = 'turn_off'

SERVICE_VOLUME_UP = "volume_up"
SERVICE_VOLUME_DOWN = "volume_down"
SERVICE_VOLUME_MUTE = "volume_mute"
SERVICE_MEDIA_PLAY_PAUSE = "media_play_pause"
SERVICE_MEDIA_PLAY = "media_play"
SERVICE_MEDIA_PAUSE = "media_pause"
SERVICE_MEDIA_NEXT_TRACK = "media_next_track"
SERVICE_MEDIA_PREV_TRACK = "media_prev_track"

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Loads up the module to call the is_on method.
    If there is no entity id given we will check all. """
    if entity_id:
        group = get_component('group')

        entity_ids = group.expand_entity_ids(hass, [entity_id])
    else:
        entity_ids = hass.states.entity_ids()

    for entity_id in entity_ids:
        domain = util.split_entity_id(entity_id)[0]

        module = get_component(domain)

        try:
            if module.is_on(hass, entity_id):
                return True

        except AttributeError:
            # module is None or method is_on does not exist
            _LOGGER.exception("Failed to call %s.is_on for %s",
                              module, entity_id)

    return False


def turn_on(hass, entity_id=None, **service_data):
    """ Turns specified entity on if possible. """
    if entity_id is not None:
        service_data[ATTR_ENTITY_ID] = entity_id

    hass.call_service(ha.DOMAIN, SERVICE_TURN_ON, service_data)


def turn_off(hass, entity_id=None, **service_data):
    """ Turns specified entity off. """
    if entity_id is not None:
        service_data[ATTR_ENTITY_ID] = entity_id

    hass.call_service(ha.DOMAIN, SERVICE_TURN_OFF, service_data)


def extract_entity_ids(hass, service):
    """
    Helper method to extract a list of entity ids from a service call.
    Will convert group entity ids to the entity ids it represents.
    """
    entity_ids = []

    if service.data and ATTR_ENTITY_ID in service.data:
        group = get_component('group')

        # Entity ID attr can be a list or a string
        service_ent_id = service.data[ATTR_ENTITY_ID]
        if isinstance(service_ent_id, list):
            ent_ids = service_ent_id
        else:
            ent_ids = [service_ent_id]

        entity_ids.extend(
            ent_id for ent_id
            in group.expand_entity_ids(hass, ent_ids)
            if ent_id not in entity_ids)

    return entity_ids


class ToggleDevice(object):
    """ ABC for devices that can be turned on and off. """
    # pylint: disable=no-self-use

    entity_id = None

    def get_name(self):
        """ Returns the name of the device if any. """
        return None

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        pass

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        pass

    def is_on(self):
        """ True if device is on. """
        return False

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return {}

    def update(self):
        """ Retrieve latest state from the real device. """
        pass

    def update_ha_state(self, hass, force_refresh=False):
        """
        Updates Home Assistant with current state of device.
        If force_refresh == True will update device before setting state.
        """
        if self.entity_id is None:
            raise ha.NoEntitySpecifiedError(
                "No entity specified for device {}".format(self.get_name()))

        if force_refresh:
            self.update()

        state = STATE_ON if self.is_on() else STATE_OFF

        return hass.states.set(self.entity_id, state,
                               self.get_state_attributes())


# pylint: disable=unused-argument
def setup(hass, config):
    """ Setup general services related to homeassistant. """

    def handle_turn_service(service):
        """ Method to handle calls to homeassistant.turn_on/off. """
        entity_ids = extract_entity_ids(hass, service)

        # Generic turn on/off method requires entity id
        if not entity_ids:
            _LOGGER.error(
                "homeassistant/%s cannot be called without entity_id",
                service.service)
            return

        # Group entity_ids by domain. groupby requires sorted data.
        by_domain = it.groupby(sorted(entity_ids),
                               lambda item: util.split_entity_id(item)[0])

        for domain, ent_ids in by_domain:
            # Create a new dict for this call
            data = dict(service.data)

            # ent_ids is a generator, convert it to a list.
            data[ATTR_ENTITY_ID] = list(ent_ids)

            hass.call_service(domain, service.service, data)

    hass.services.register(ha.DOMAIN, SERVICE_TURN_OFF, handle_turn_service)
    hass.services.register(ha.DOMAIN, SERVICE_TURN_ON, handle_turn_service)

    return True
