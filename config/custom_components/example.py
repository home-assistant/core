"""
custom_components.example
~~~~~~~~~~~~~~~~~~~~~~~~~

Example component to target an entity_id to:
 - turn it on at 7AM in the morning
 - turn it on if anyone comes home and it is off
 - turn it off if all lights are turned off
 - turn it off if all people leave the house
 - offer a service to turn it on for 10 seconds

Configuration:

To use the Example custom component you will need to add the following to
your config/configuration.yaml

example:
  target: TARGET_ENTITY

Variable:

target
*Required
TARGET_ENTITY should be one of your devices that can be turned on and off,
ie a light or a switch. Example value could be light.Ceiling or switch.AC
(if you have these devices with those names).
"""
import time
import logging

from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_ON, STATE_OFF
import homeassistant.loader as loader
from homeassistant.helpers import validate_config
import homeassistant.components as core

# The domain of your component. Should be equal to the name of your component
DOMAIN = "example"

# List of component names (string) your component depends upon
# We depend on group because group will be loaded after all the components that
# initialize devices have been setup.
DEPENDENCIES = ['group']

# Configuration key for the entity id we are targetting
CONF_TARGET = 'target'

# Name of the service that we expose
SERVICE_FLASH = 'flash'

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """ Setup example component. """

    # Validate that all required config options are given
    if not validate_config(config, {DOMAIN: [CONF_TARGET]}, _LOGGER):
        return False

    target_id = config[DOMAIN][CONF_TARGET]

    # Validate that the target entity id exists
    if hass.states.get(target_id) is None:
        _LOGGER.error("Target entity id %s does not exist", target_id)

        # Tell the bootstrapper that we failed to initialize
        return False

    # We will use the component helper methods to check the states.
    device_tracker = loader.get_component('device_tracker')
    light = loader.get_component('light')

    def track_devices(entity_id, old_state, new_state):
        """ Called when the group.all devices change state. """

        # If anyone comes home and the core is not on, turn it on.
        if new_state.state == STATE_HOME and not core.is_on(hass, target_id):

            core.turn_on(hass, target_id)

        # If all people leave the house and the core is on, turn it off
        elif new_state.state == STATE_NOT_HOME and core.is_on(hass, target_id):

            core.turn_off(hass, target_id)

    # Register our track_devices method to receive state changes of the
    # all tracked devices group.
    hass.states.track_change(
        device_tracker.ENTITY_ID_ALL_DEVICES, track_devices)

    def wake_up(now):
        """ Turn it on in the morning if there are people home and
            it is not already on. """

        if device_tracker.is_on(hass) and not core.is_on(hass, target_id):
            _LOGGER.info('People home at 7AM, turning it on')
            core.turn_on(hass, target_id)

    # Register our wake_up service to be called at 7AM in the morning
    hass.track_time_change(wake_up, hour=7, minute=0, second=0)

    def all_lights_off(entity_id, old_state, new_state):
        """ If all lights turn off, turn off. """

        if core.is_on(hass, target_id):
            _LOGGER.info('All lights have been turned off, turning it off')
            core.turn_off(hass, target_id)

    # Register our all_lights_off method to be called when all lights turn off
    hass.states.track_change(
        light.ENTITY_ID_ALL_LIGHTS, all_lights_off, STATE_ON, STATE_OFF)

    def flash_service(call):
        """ Service that will turn the target off for 10 seconds
            if on and vice versa. """

        if core.is_on(hass, target_id):
            core.turn_off(hass, target_id)

            time.sleep(10)

            core.turn_on(hass, target_id)

        else:
            core.turn_on(hass, target_id)

            time.sleep(10)

            core.turn_off(hass, target_id)

    # Register our service with HASS.
    hass.services.register(DOMAIN, SERVICE_FLASH, flash_service)

    # Tells the bootstrapper that the component was successfully initialized
    return True
