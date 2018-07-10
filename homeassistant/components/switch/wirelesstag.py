"""
Switch implementation for Wireless Sensor Tags (wirelesstag.net) platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wirelesstag/
"""
import logging

import voluptuous as vol


from homeassistant.components.wirelesstag import (
    DOMAIN as WIRELESSTAG_DOMAIN,
    WIRELESSTAG_TYPE_13BIT, WIRELESSTAG_TYPE_WATER,
    WIRELESSTAG_TYPE_ALSPRO,
    WIRELESSTAG_TYPE_WEMO_DEVICE,
    WirelessTagBaseSensor)
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS)
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['wirelesstag']

_LOGGER = logging.getLogger(__name__)

ARM_TEMPERATURE = 'temperature'
ARM_HUMIDITY = 'humidity'
ARM_MOTION = 'motion'
ARM_LIGHT = 'light'
ARM_MOISTURE = 'moisture'

# Switch types: Name, tag sensor type
SWITCH_TYPES = {
    ARM_TEMPERATURE: ['Arm Temperature', 'temperature'],
    ARM_HUMIDITY: ['Arm Humidity', 'humidity'],
    ARM_MOTION: ['Arm Motion', 'motion'],
    ARM_LIGHT: ['Arm Light', 'light'],
    ARM_MOISTURE: ['Arm Moisture', 'moisture']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SWITCH_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up switches for a Wireless Sensor Tags."""
    platform = hass.data.get(WIRELESSTAG_DOMAIN)

    switches = []
    tags = platform.load_tags()
    for switch_type in config.get(CONF_MONITORED_CONDITIONS):
        for _, tag in tags.items():
            if switch_type in WirelessTagSwitch.allowed_switches(tag):
                switches.append(WirelessTagSwitch(platform, tag, switch_type))

    add_devices(switches, True)


class WirelessTagSwitch(WirelessTagBaseSensor, SwitchDevice):
    """A switch implementation for Wireless Sensor Tags."""

    @classmethod
    def allowed_switches(cls, tag):
        """Return allowed switch types for wireless tag."""
        all_sensors = SWITCH_TYPES.keys()
        sensors_per_tag_spec = {
            WIRELESSTAG_TYPE_13BIT: [
                ARM_TEMPERATURE, ARM_HUMIDITY, ARM_MOTION],
            WIRELESSTAG_TYPE_WATER: [
                ARM_TEMPERATURE, ARM_MOISTURE],
            WIRELESSTAG_TYPE_ALSPRO: [
                ARM_TEMPERATURE, ARM_HUMIDITY, ARM_MOTION, ARM_LIGHT],
            WIRELESSTAG_TYPE_WEMO_DEVICE: []
        }

        tag_type = tag.tag_type

        result = (
            sensors_per_tag_spec[tag_type]
            if tag_type in sensors_per_tag_spec else all_sensors)
        _LOGGER.info("Allowed switches: %s tag_type: %s",
                     str(result), tag_type)

        return result

    def __init__(self, api, tag, switch_type):
        """Initialize a switch for Wireless Sensor Tag."""
        super().__init__(api, tag)
        self._switch_type = switch_type
        self.sensor_type = SWITCH_TYPES[self._switch_type][1]
        self._name = '{} {}'.format(self._tag.name,
                                    SWITCH_TYPES[self._switch_type][0])

    def turn_on(self, **kwargs):
        """Turn on the switch."""
        self._api.arm(self)

    def turn_off(self, **kwargs):
        """Turn on the switch."""
        self._api.disarm(self)

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._state

    def updated_state_value(self):
        """Provide formatted value."""
        return self.principal_value

    @property
    def principal_value(self):
        """Provide actual value of switch."""
        attr_name = 'is_{}_sensor_armed'.format(self.sensor_type)
        return getattr(self._tag, attr_name, False)
