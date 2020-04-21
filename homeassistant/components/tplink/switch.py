"""Support for TPLink HS100/HS110/HS200 smart switch."""
import logging
import time
from typing import Union

from kasa import SmartDeviceException, SmartPlug, SmartStrip

from homeassistant.components.switch import (
    ATTR_CURRENT_POWER_W,
    ATTR_TODAY_ENERGY_KWH,
    SwitchEntity,
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


async def add_entity(device: Union[SmartPlug, SmartStrip], async_add_entities):
    """Check if device is online and add the entity."""
    # Attempt to get the sysinfo. If it fails, it will raise an
    # exception that is caught by async_add_entities_retry which
    # will try again later.
    await device.update()

    entities = []
    if device.is_strip:
        children = [SmartPlugSwitch(plug, should_poll=False) for plug in device.plugs]
        _LOGGER.debug("Found strip %s with %s children", device, len(children))
        entities.extend(children)
        strip = SmartPlugSwitch(device, children=children)
        entities.append(strip)
    else:
        entities.append(SmartPlugSwitch(device))

    _LOGGER.debug("Adding switch entities: %s", entities)
    async_add_entities(entities, update_before_add=True)


async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    """Set up switches."""
    await async_add_entities_retry(
        hass, async_add_entities, hass.data[TPLINK_DOMAIN][CONF_SWITCH], add_entity
    )

    return True


class SmartPlugSwitch(SwitchEntity):
    """Representation of a TPLink Smart Plug switch."""

    def __init__(self, smartplug: SmartPlug, children=None, should_poll=True):
        """Initialize the switch."""
        self.smartplug = smartplug
        self._available = False
        self._emeter_params = {}
        self._should_poll = should_poll
        self._children = children or []

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        Only parent devices need to be polled for smart strips.
        """
        return self._should_poll

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self.smartplug.device_id

    @property
    def name(self):
        """Return the name of the Smart Plug."""
        return self.smartplug.alias

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self.smartplug.alias,
            "model": self.smartplug.model,
            "manufacturer": "TP-Link",
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.smartplug.mac)},
            "sw_version": self.smartplug.sys_info["sw_ver"],
        }

    @property
    def available(self) -> bool:
        """Return if switch is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.smartplug.is_on

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.smartplug.turn_on()
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.smartplug.turn_off()
        await self.async_update_ha_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._emeter_params

    async def async_update(self):
        """Update the TP-Link switch's state."""
        _LOGGER.debug("Going to update %s", self.name)
        try:
            if self.should_poll:
                await self.smartplug.update()

            if self.smartplug.has_emeter:
                emeter_readings = await self.smartplug.get_emeter_realtime()

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

                emeter_statics = await self.smartplug.get_emeter_daily()
                try:
                    self._emeter_params[ATTR_TODAY_ENERGY_KWH] = "{:.3f}".format(
                        emeter_statics[int(time.strftime("%e"))]
                    )
                except KeyError:
                    # Device returned no daily history
                    pass

            self._available = True

            _LOGGER.debug(
                "Going to update %s children for %s: %s",
                len(self._children),
                self.name,
                self._children,
            )
            for child in self._children:
                child.async_schedule_update_ha_state(force_refresh=True)

        except (SmartDeviceException, OSError) as ex:
            if self._available:
                _LOGGER.warning(
                    "Could not read state for %s: %s", self.smartplug.host, ex
                )
            self._available = False
