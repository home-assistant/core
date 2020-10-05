"""Support for TaHoma switches."""
import logging
from typing import Optional

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    DOMAIN as SWITCH,
    SwitchEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON

from .const import COMMAND_OFF, COMMAND_ON, CORE_ON_OFF_STATE, DOMAIN
from .tahoma_device import TahomaDevice

_LOGGER = logging.getLogger(__name__)

COMMAND_CYCLE = "cycle"
COMMAND_MEMORIZED_VOLUME = "memorizedVolume"
COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE = "ringWithSingleSimpleSequence"
COMMAND_SET_FORCE_HEATING = "setForceHeating"
COMMAND_STANDARD = "standard"

IO_FORCE_HEATING_STATE = "io:ForceHeatingState"

DEVICE_CLASS_SIREN = "siren"

ICON_BELL_RING = "mdi:bell-ring"
ICON_BELL_OFF = "mdi:bell-off"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        TahomaSwitch(device.deviceurl, coordinator)
        for device in data["entities"].get(SWITCH)
    ]

    async_add_entities(entities)


class TahomaSwitch(TahomaDevice, SwitchEntity):
    """Representation a TaHoma Switch."""

    @property
    def device_class(self):
        """Return the class of the device."""
        if self.device.ui_class == "Siren":
            return DEVICE_CLASS_SIREN

        return DEVICE_CLASS_SWITCH

    @property
    def icon(self) -> Optional[str]:
        """Return the icon to use in the frontend, if any."""
        if self.device_class == DEVICE_CLASS_SIREN:
            if self.is_on:
                return ICON_BELL_RING
            return ICON_BELL_OFF

        return None

    async def async_turn_on(self, **_):
        """Send the on command."""
        if self.has_command(COMMAND_ON):
            await self.async_execute_command(COMMAND_ON)

        elif self.has_command(COMMAND_SET_FORCE_HEATING):
            await self.async_execute_command(COMMAND_SET_FORCE_HEATING, STATE_ON)

        elif self.has_command(COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE):
            await self.async_execute_command(
                COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE,  # https://www.tahomalink.com/enduser-mobile-web/steer-html5-client/vendor/somfy/io/siren/const.js
                2 * 60 * 1000,  # 2 minutes
                75,  # 90 seconds bip, 30 seconds silence
                2,  # repeat 3 times
                COMMAND_MEMORIZED_VOLUME,
            )

    async def async_turn_off(self, **_):
        """Send the off command."""
        if self.has_command(COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE):
            await self.async_execute_command(
                COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE,
                2000,
                100,
                0,
                COMMAND_STANDARD,
            )

        elif self.has_command(COMMAND_SET_FORCE_HEATING):
            await self.async_execute_command(COMMAND_SET_FORCE_HEATING, STATE_OFF)

        elif self.has_command(COMMAND_OFF):
            await self.async_execute_command(COMMAND_OFF)

    async def async_toggle(self, **_):
        """Click the switch."""
        if self.has_command(COMMAND_CYCLE):
            await self.async_execute_command(COMMAND_CYCLE)

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        return self.select_state(CORE_ON_OFF_STATE, IO_FORCE_HEATING_STATE) == STATE_ON
