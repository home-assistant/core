"""
Support for TPLink HS100/HS110/HS200 smart switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tplink/
"""
import logging
import time

import voluptuous as vol

from homeassistant.components.switch import (
    SwitchDevice, PLATFORM_SCHEMA, ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH)
from homeassistant.const import (CONF_HOST, CONF_NAME, ATTR_VOLTAGE)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyHS100==0.3.2']

_LOGGER = logging.getLogger(__name__)

ATTR_TOTAL_ENERGY_KWH = 'total_energy_kwh'
ATTR_CURRENT_A = 'current_a'

CONF_LEDS = 'enable_leds'

DEFAULT_NAME = 'TP-Link Switch'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_LEDS): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the TPLink switch platform."""
    from pyHS100 import SmartPlug
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    leds_on = config.get(CONF_LEDS)

    add_devices([SmartPlugSwitch(SmartPlug(host), name, leds_on)], True)


class SmartPlugSwitch(SwitchDevice):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(self, smartplug, name, leds_on):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._name = name
        self._leds_on = leds_on
        self._state = None
        self._available = True
        # Set up emeter cache
        self._emeter_params = {}

    @property
    def name(self):
        """Return the name of the Smart Plug, if any."""
        return self._name

    @property
    def available(self) -> bool:
        """Return if switch is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.smartplug.turn_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.smartplug.turn_off()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._emeter_params

    def update(self):
        """Update the TP-Link switch's state."""
        from pyHS100 import SmartDeviceException
        try:
            self._state = self.smartplug.state == \
                self.smartplug.SWITCH_STATE_ON

            if self._leds_on is not None:
                self.smartplug.led = self._leds_on
                self._leds_on = None

            # Pull the name from the device if a name was not specified
            if self._name == DEFAULT_NAME:
                self._name = self.smartplug.alias

            if self.smartplug.has_emeter:
                emeter_readings = self.smartplug.get_emeter_realtime()

                self._emeter_params[ATTR_CURRENT_POWER_W] \
                    = "{:.2f}".format(emeter_readings["power"])
                self._emeter_params[ATTR_TOTAL_ENERGY_KWH] \
                    = "{:.3f}".format(emeter_readings["total"])
                self._emeter_params[ATTR_VOLTAGE] \
                    = "{:.1f}".format(emeter_readings["voltage"])
                self._emeter_params[ATTR_CURRENT_A] \
                    = "{:.2f}".format(emeter_readings["current"])

                emeter_statics = self.smartplug.get_emeter_daily()
                try:
                    self._emeter_params[ATTR_TODAY_ENERGY_KWH] \
                        = "{:.3f}".format(
                            emeter_statics[int(time.strftime("%e"))])
                except KeyError:
                    # Device returned no daily history
                    pass

            self._available = True

        except (SmartDeviceException, OSError) as ex:
            if self._available:
                _LOGGER.warning(
                    "Could not read state for %s: %s", self.name, ex)
                self._available = False
