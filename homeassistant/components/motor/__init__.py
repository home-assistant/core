"""
homeassistant.components.motor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Motor component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/motor/
"""
import os
import logging

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.components import group
from homeassistant.const import (
    SERVICE_OPEN, SERVICE_CLOSE, SERVICE_STOP,
    STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN, ATTR_ENTITY_ID)


DOMAIN = 'motor'
SCAN_INTERVAL = 15

GROUP_NAME_ALL_MOTORS = 'all motors'
ENTITY_ID_ALL_MOTORS = group.ENTITY_ID_FORMAT.format('all_motors')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {}

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POSITION = 'current_position'


def is_open(hass, entity_id=None):
    """ Returns if the motor is open based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_MOTORS
    return hass.states.is_state(entity_id, STATE_OPEN)


def call_open(hass, entity_id=None):
    """ Open all or specified motor. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_OPEN, data)


def call_close(hass, entity_id=None):
    """ Close all or specified motor. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_CLOSE, data)


def call_stop(hass, entity_id=None):
    """ Stops all or specified motor. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_STOP, data)


def setup(hass, config):
    """ Track states and offer events for motors. """
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_MOTORS)
    component.setup(config)

    def handle_motor_service(service):
        """ Handles calls to the motor services. """
        target_motors = component.extract_from_service(service)

        for motor in target_motors:
            if service.service == SERVICE_OPEN:
                motor.open()
            elif service.service == SERVICE_CLOSE:
                motor.close()
            elif service.service == SERVICE_STOP:
                motor.stop()

            if motor.should_poll:
                motor.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_OPEN,
                           handle_motor_service,
                           descriptions.get(SERVICE_OPEN))
    hass.services.register(DOMAIN, SERVICE_CLOSE,
                           handle_motor_service,
                           descriptions.get(SERVICE_CLOSE))
    hass.services.register(DOMAIN, SERVICE_STOP,
                           handle_motor_service,
                           descriptions.get(SERVICE_STOP))

    return True


class MotorDevice(Entity):
    """ Represents a motor within Home Assistant. """
    # pylint: disable=no-self-use

    @property
    def current_position(self):
        """
        Return current position of motor.
        None is unknown, 0 is closed, 100 is fully open.
        """
        raise NotImplementedError()

    @property
    def state(self):
        """ Returns the state of the motor. """
        current = self.current_position

        if current is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if current == 0 else STATE_OPEN

    @property
    def state_attributes(self):
        """ Return the state attributes. """
        current = self.current_position

        if current is None:
            return None

        return {
            ATTR_CURRENT_POSITION: current
        }

    def open(self, **kwargs):
        """ Open the motor. """
        raise NotImplementedError()

    def close(self, **kwargs):
        """ Close the motor. """
        raise NotImplementedError()

    def stop(self, **kwargs):
        """ Stop the motor. """
        raise NotImplementedError()
