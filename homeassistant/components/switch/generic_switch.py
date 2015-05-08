"""
A generic switch that can be created by other componenets during setup
"""
import logging

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.loader import get_component

from homeassistant.const import (
    STATE_ON, STATE_OFF,
    ATTR_DOMAIN, EVENT_STATE_CHANGED)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the GenericSwitch platform. """
    logger = logging.getLogger(__name__)

    if discovery_info is not None:
        parent_domain = discovery_info.get(ATTR_DOMAIN, None)
        parent_component = get_component(parent_domain)

        if parent_component is None:
            logger.error(
                'Could not find parent component {0}'.format(parent_domain))
            return

        parent_entity_id = discovery_info.get('entity_id', None)
        name = discovery_info.get('name', parent_entity_id + ' Switch')

        devices = []
        devices.append(GenericSwitch(hass, name, discovery_info))
        add_devices(devices)

    return True


# pylint: disable=too-many-instance-attributes
class GenericSwitch(ToggleEntity):
    """ A generic switch the can be created during setup of another component
    and will watch the state of a specified variable """
    def __init__(self, hass, name, info=None, state=STATE_OFF):
        info = {} if info is None else info
        self._state = state
        self._name = name
        self._info = info
        self._parent_entity_id = info.get('entity_id', None)
        self._parent_entity_domain = info.get(ATTR_DOMAIN, None)
        self._parent_action = info.get('parent_action', None)
        self._watched_parent_attribute = info.get('watched_attribute', 'state')
        self.hass = hass
        self._logger = logging.getLogger(__name__)

        self.hass.bus.listen(
            EVENT_STATE_CHANGED,
            self.process_parent_entity_change)

    def process_parent_entity_change(self, event):
        """ Handle changes to the state of the linked parent entity """
        if not event or not event.data:
            return
        new_state = event.data['new_state']

        if new_state.entity_id == self._parent_entity_id:
            watched_val = new_state.attributes.get(
                self._watched_parent_attribute,
                None)
            msg = 'The child entity {0} is now watching the \
            value {1} on the parent entity {2}'
            msg.format(
                self.entity_id,
                self._watched_parent_attribute,
                self._parent_entity_id)

            self._logger.info(msg)

            if watched_val is STATE_ON or watched_val is STATE_OFF:
                self._state = watched_val
            elif watched_val is True:
                self._state = STATE_ON
            elif watched_val is False:
                self._state = STATE_OFF

            self.update_ha_state(True)

    @property
    def name(self):
        """ Returns the name of the entity. """
        return self._name

    @property
    def is_on(self):
        """ True if entity is on. """
        return True if self._state == STATE_ON else False

    def turn_on(self, **kwargs):
        """ Turn the entity on. """
        self._state = STATE_ON

    def turn_off(self, **kwargs):
        """ Turn the entity off. """
        self._state = STATE_OFF

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = super().state_attributes
        attr['parent_entity_id'] = self._parent_entity_id
        attr['parent_entity_domain'] = self._parent_entity_domain
        attr['parent_action'] = self._parent_action
        return attr
