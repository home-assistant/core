"""
homeassistant.components.simple_alarm
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Intruder alerts component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/simple_alarm/
"""
import logging

import homeassistant.loader as loader
from homeassistant.helpers.event import track_state_change
from homeassistant.const import STATE_ON, STATE_OFF, STATE_HOME, STATE_NOT_HOME

DOMAIN = "simple_alarm"

DEPENDENCIES = ['group', 'device_tracker', 'light']

# Attribute to tell which light has to flash whem a known person comes home
# If omitted will flash all.
CONF_KNOWN_LIGHT = "known_light"

# Attribute to tell which light has to flash whem an unknown person comes home
# If omitted will flash all.
CONF_UNKNOWN_LIGHT = "unknown_light"

# Services to test the alarms
SERVICE_TEST_KNOWN_ALARM = "test_known"
SERVICE_TEST_UNKNOWN_ALARM = "test_unknown"


def setup(hass, config):
    """ Sets up the simple alarms. """
    logger = logging.getLogger(__name__)

    device_tracker = loader.get_component('device_tracker')
    light = loader.get_component('light')
    notify = loader.get_component('notify')

    light_ids = []

    for conf_key in (CONF_KNOWN_LIGHT, CONF_UNKNOWN_LIGHT):
        light_id = config[DOMAIN].get(conf_key) or light.ENTITY_ID_ALL_LIGHTS

        if hass.states.get(light_id) is None:
            logger.error(
                'Light id %s could not be found in state machine', light_id)

            return False

        else:
            light_ids.append(light_id)

    # pylint: disable=unbalanced-tuple-unpacking
    known_light_id, unknown_light_id = light_ids

    if hass.states.get(device_tracker.ENTITY_ID_ALL_DEVICES) is None:
        logger.error('No devices are being tracked, cannot setup alarm')

        return False

    def known_alarm():
        """ Fire an alarm if a known person arrives home. """
        light.turn_on(hass, known_light_id, flash=light.FLASH_SHORT)

    def unknown_alarm():
        """ Fire an alarm if the light turns on while no one is home. """
        light.turn_on(
            hass, unknown_light_id,
            flash=light.FLASH_LONG, rgb_color=[255, 0, 0])

        # Send a message to the user
        notify.send_message(
            hass, "The lights just got turned on while no one was home.")

    # Setup services to test the effect
    hass.services.register(
        DOMAIN, SERVICE_TEST_KNOWN_ALARM, lambda call: known_alarm())
    hass.services.register(
        DOMAIN, SERVICE_TEST_UNKNOWN_ALARM, lambda call: unknown_alarm())

    def unknown_alarm_if_lights_on(entity_id, old_state, new_state):
        """ Called when a light has been turned on. """
        if not device_tracker.is_on(hass):
            unknown_alarm()

    track_state_change(
        hass, light.ENTITY_ID_ALL_LIGHTS,
        unknown_alarm_if_lights_on, STATE_OFF, STATE_ON)

    def ring_known_alarm(entity_id, old_state, new_state):
        """ Called when a known person comes home. """
        if light.is_on(hass, known_light_id):
            known_alarm()

    # Track home coming of each device
    track_state_change(
        hass, hass.states.entity_ids(device_tracker.DOMAIN),
        ring_known_alarm, STATE_NOT_HOME, STATE_HOME)

    return True
