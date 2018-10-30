"""
Support for TPLink HS100/HS110/HS200 smart switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tplink/
"""
import logging
import time

from homeassistant.components.switch import (
    SwitchDevice, ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH)
from homeassistant.components.tplink import DOMAIN as TPLINK_DOMAIN
from homeassistant.const import ATTR_VOLTAGE
from homeassistant.exceptions import PlatformNotReady

DEPENDENCIES = ['tplink']

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

ATTR_TOTAL_ENERGY_KWH = 'total_energy_kwh'
ATTR_CURRENT_A = 'current_a'


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up discovered switches."""
    from pyHS100 import SmartDeviceException
    devs = []
    for dev in hass.data[TPLINK_DOMAIN]['switch']:
        try:
            # fetch MAC and name already now to avoid I/O inside init
            unique_id = dev.sys_info['mac']
            name = dev.alias
            devs.append(SmartPlugSwitch(dev, unique_id, name, leds_on=None))
        except SmartDeviceException as ex:
            _LOGGER.error("Unable to fetch data from the device: %s", ex)
            raise PlatformNotReady

    async_add_devices(devs, True)


class SmartPlugSwitch(SwitchDevice):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(self, smartplug, unique_id, name, leds_on):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._unique_id = unique_id
        self._name = name
        self._leds_on = leds_on
        self._state = None
        self._available = True
        # Set up emeter cache
        self._emeter_params = {}

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the Smart Plug."""
        return self._name

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            'identifiers': {
                (TPLINK_DOMAIN, self._unique_id)
            },
            'name': self._name,
            'model': self.smartplug.model,
            'manufacturer': 'TP-Link',
            'sw_version': self.smartplug.sys_info["sw_ver"],
            'hw_version': self.smartplug.sys_info["hw_ver"],
        }

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
