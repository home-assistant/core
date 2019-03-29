"""
Support for TPLink HS100/HS110/HS200 smart switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tplink/
"""
import logging
import time

from homeassistant.components.switch import (
    ATTR_CURRENT_POWER_W, ATTR_TODAY_ENERGY_KWH, SwitchDevice)
from homeassistant.const import ATTR_VOLTAGE
import homeassistant.helpers.device_registry as dr

from . import CONF_SWITCH, DOMAIN as TPLINK_DOMAIN

DEPENDENCIES = ['tplink']

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

ATTR_TOTAL_ENERGY_KWH = 'total_energy_kwh'
ATTR_CURRENT_A = 'current_a'


def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the platform.

    Deprecated.
    """
    _LOGGER.warning('Loading as a platform is no longer supported, '
                    'convert to use the tplink component.')


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up discovered switches."""
    devs = []
    for dev in hass.data[TPLINK_DOMAIN][CONF_SWITCH]:
        devs.append(SmartPlugSwitch(dev))

    async_add_entities(devs, True)

    return True


class SmartPlugSwitch(SwitchDevice):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(self, smartplug):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._sysinfo = None
        self._state = None
        self._available = False
        # Set up emeter cache
        self._emeter_params = {}

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._sysinfo["mac"]

    @property
    def name(self):
        """Return the name of the Smart Plug."""
        return self._sysinfo["alias"]

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self.name,
            "model": self._sysinfo["model"],
            "manufacturer": 'TP-Link',
            "connections": {
                (dr.CONNECTION_NETWORK_MAC, self._sysinfo["mac"])
            },
            "sw_version": self._sysinfo["sw_ver"],
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
            if not self._sysinfo:
                self._sysinfo = self.smartplug.sys_info

            self._state = self.smartplug.state == \
                self.smartplug.SWITCH_STATE_ON

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
                _LOGGER.warning("Could not read state for %s: %s",
                                self.smartplug.host, ex)
            self._available = False
