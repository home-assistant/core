"""Support for TPLink HS100/HS110/HS200 smart switch."""
import logging
import time

from pyHS100 import SmartDeviceException, SmartPlug

from homeassistant.components.switch import (
    ATTR_CURRENT_POWER_W,
    ATTR_TODAY_ENERGY_KWH,
    SwitchDevice,
)
from homeassistant.const import ATTR_VOLTAGE
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.typing import HomeAssistantType

from . import CONF_SWITCH, DOMAIN as TPLINK_DOMAIN
from .common import async_add_entities_retry

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

ATTR_TOTAL_ENERGY_KWH = "total_energy_kwh"
ATTR_CURRENT_A = "current_a"


def add_entity(device: SmartPlug, async_add_entities):
    """Check if device is online and add the entity."""
    # Attempt to get the sysinfo. If it fails, it will raise an
    # exception that is caught by async_add_entities_retry which
    # will try again later.
    device.get_sysinfo()

    async_add_entities([SmartPlugSwitch(device)], update_before_add=True)


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    """Set up switches."""
    await async_add_entities_retry(
        hass, async_add_entities, hass.data[TPLINK_DOMAIN][CONF_SWITCH], add_entity
    )

    return True


class SmartPlugSwitch(SwitchDevice):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(self, smartplug: SmartPlug):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._sysinfo = None
        self._state = None
        self._available = False
        # Set up emeter cache
        self._emeter_params = {}

        self._mac = None
        self._alias = None
        self._model = None
        self._device_id = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device_id

    @property
    def name(self):
        """Return the name of the Smart Plug."""
        return self._alias

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self._alias,
            "model": self._model,
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._mac)},
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

    @property
    def _plug_from_context(self):
        """Return the plug from the context."""
        children = self.smartplug.sys_info["children"]
        return next(c for c in children if c["id"] == self.smartplug.context)

    def update(self):
        """Update the TP-Link switch's state."""
        try:
            if not self._sysinfo:
                self._sysinfo = self.smartplug.sys_info
                self._mac = self.smartplug.mac
                self._model = self.smartplug.model
                if self.smartplug.context is None:
                    self._alias = self.smartplug.alias
                    self._device_id = self._mac
                else:
                    self._alias = self._plug_from_context["alias"]
                    self._device_id = self.smartplug.context

            if self.smartplug.context is None:
                self._state = self.smartplug.state == self.smartplug.SWITCH_STATE_ON
            else:
                self._state = self._plug_from_context["state"] == 1

            if self.smartplug.has_emeter:
                emeter_readings = self.smartplug.get_emeter_realtime()

                self._emeter_params[ATTR_CURRENT_POWER_W] = "{:.2f}".format(
                    emeter_readings["power"]
                )
                self._emeter_params[ATTR_TOTAL_ENERGY_KWH] = "{:.3f}".format(
                    emeter_readings["total"]
                )
                self._emeter_params[ATTR_VOLTAGE] = "{:.1f}".format(
                    emeter_readings["voltage"]
                )
                self._emeter_params[ATTR_CURRENT_A] = "{:.2f}".format(
                    emeter_readings["current"]
                )

                emeter_statics = self.smartplug.get_emeter_daily()
                try:
                    self._emeter_params[ATTR_TODAY_ENERGY_KWH] = "{:.3f}".format(
                        emeter_statics[int(time.strftime("%e"))]
                    )
                except KeyError:
                    # Device returned no daily history
                    pass

            self._available = True

        except (SmartDeviceException, OSError) as ex:
            if self._available:
                _LOGGER.warning(
                    "Could not read state for %s: %s", self.smartplug.host, ex
                )
            self._available = False
