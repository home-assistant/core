"""Support for TaHoma switches."""
import logging

from homeassistant.components.switch import (
    DEVICE_CLASS_SWITCH,
    DOMAIN as SWITCH,
    SwitchEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON

from .const import COMMAND_OFF, COMMAND_ON, CORE_ON_OFF_STATE, DOMAIN
from .tahoma_entity import TahomaEntity

_LOGGER = logging.getLogger(__name__)

COMMAND_CYCLE = "cycle"
COMMAND_MEMORIZED_VOLUME = "memorizedVolume"
COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE = "ringWithSingleSimpleSequence"
COMMAND_SET_FORCE_HEATING = "setForceHeating"
COMMAND_STANDARD = "standard"

IO_FORCE_HEATING_STATE = "io:ForceHeatingState"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the TaHoma sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities = [
        TahomaSwitch(device.deviceurl, coordinator)
        for device in data["platforms"][SWITCH]
    ]

    async_add_entities(entities)


class TahomaSwitch(TahomaEntity, SwitchEntity):
    """Representation of a TaHoma Switch."""

    @property
    def device_class(self):
        """Return the class of the device."""
        return DEVICE_CLASS_SWITCH

    @property
    def is_on(self):
        """Get whether the switch is in on state."""
        return (
            self.executor.select_state(CORE_ON_OFF_STATE, IO_FORCE_HEATING_STATE)
            == STATE_ON
        )

    async def async_turn_on(self, **_):
        """Send the on command."""
        if self.executor.has_command(COMMAND_ON):
            await self.executor.async_execute_command(COMMAND_ON)

        elif self.executor.has_command(COMMAND_SET_FORCE_HEATING):
            await self.executor.async_execute_command(
                COMMAND_SET_FORCE_HEATING, STATE_ON
            )

        elif self.executor.has_command(COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE):
            await self.executor.async_execute_command(
                COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE,  # https://www.tahomalink.com/enduser-mobile-web/steer-html5-client/vendor/somfy/io/siren/const.js
                2 * 60 * 1000,  # 2 minutes
                75,  # 90 seconds bip, 30 seconds silence
                2,  # repeat 3 times
                COMMAND_MEMORIZED_VOLUME,
            )

    async def async_turn_off(self, **_):
        """Send the off command."""
        if self.executor.has_command(COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE):
            await self.executor.async_execute_command(
                COMMAND_RING_WITH_SINGLE_SIMPLE_SEQUENCE,
                2000,
                100,
                0,
                COMMAND_STANDARD,
            )

        elif self.executor.has_command(COMMAND_SET_FORCE_HEATING):
            await self.executor.async_execute_command(
                COMMAND_SET_FORCE_HEATING, STATE_OFF
            )

        elif self.executor.has_command(COMMAND_OFF):
            await self.executor.async_execute_command(COMMAND_OFF)

    async def async_toggle(self, **_):
        """Click the switch."""
        if self.executor.has_command(COMMAND_CYCLE):
            await self.executor.async_execute_command(COMMAND_CYCLE)
