"""
Support for INSTEON PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging

_LOGGER = logging.getLogger(__name__)

EVENT_MOTION_DETECTED = 'motion_detected'
EVENT_LIGHT_DETECTED = 'light_detected'
EVENT_DARK_DETECTED = 'darK_detected'
EVENT_BATTERY_LOW = 'battery_low'
EVENT_BUTTON_PRESSED = 'button_pressed'
EVENT_CONF_BUTTON = 'button'

def fire_motion_detected_event(device, group, val):
    # Firing an event when motion is detected.
    if val:
        _LOGGER.debug('Firing event {}.{}'.format(DOMAIN, EVENT_MOTION_DETECTED))
        self.hass.bus.fire('{}.{}'.format(DOMAIN, EVENT_MOTION_DETECTED), {
            CONF_ADDRESS: device.address.hex
            })

def fire_light_dark_detected_event(device, group, val):
    # Firing an event when light or dark is detected.
    if val:
        _LOGGER.debug('Firing event {}.{}'.format(DOMAIN, EVENT_DARK_DETECTED))
        self.hass.bus.fire('{}.{}'.format(DOMAIN, EVENT_DARK_DETECTED), {
            CONF_ADDRESS: device.address.hex
            })
    else:
        _LOGGER.debug('Firing event {}.{}'.format(DOMAIN, EVENT_LIGHT_DETECTED))
        self.hass.bus.fire('{}.{}'.format(DOMAIN, EVENT_LIGHT_DETECTED), {
            CONF_ADDRESS: device.address.hex
            })

def fire_battery_low_event(device, group, val):
    # Firing an event when battery low is detected.
    if not val:
        _LOGGER.debug('Firing event {}.{}'.format(DOMAIN, EVENT_BATTERY_LOW))
        button = device.states[group].name[-1].lower()
        self.hass.bus.fire('{}.{}'.format(DOMAIN, EVENT_BATTERY_LOW), {
            CONF_ADDRESS: device.address.hex,
            EVENT_CONF_BUTTON: button
            })

def fire_button_pressed_event(device, group, val):
    # Firing an event when a button is pressed.
    if val:
        _LOGGER.debug('Firing event {}.{}'.format(DOMAIN, EVENT_BUTTON_PRESSED))
        button = device.states[group].name[:-1].lower()
        self.hass.bus.fire('{}.{}'.format(DOMAIN, EVENT_BUTTON_PRESSED), {
            CONF_ADDRESS: device.address.hex,
            EVENT_CONF_BUTTON: button
            })