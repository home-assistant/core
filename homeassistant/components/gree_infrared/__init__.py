"""Gree IR Remote integration for Home Assistant."""

import asyncio
from dataclasses import dataclass, field, replace
from typing import Self

from infrared_protocols.commands.gree_ac import (
    MIN_TEMP,
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
)

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import CONF_HVAC_MODES, DEFAULT_HVAC_MODES, HA_MODE_TO_LIB

PLATFORMS = [Platform.CLIMATE]


@dataclass(frozen=True, kw_only=True)
class GreeAcState:
    """The state a Gree frame carries.

    Every frame carries the whole state, so a frame changing one field has to
    resend every other field as the unit last had it.
    """

    power: bool = False
    mode: GreeAcMode = GreeAcMode.COOL
    temperature: int = MIN_TEMP
    fan: GreeAcFanSpeed = GreeAcFanSpeed.AUTO
    turbo: bool = False
    display: bool = True
    blow: bool = False
    swing_v: bool = False
    swing_h: bool = False

    @classmethod
    def from_command(cls, command: GreeAcCommand) -> Self:
        """Build the state a received frame describes."""
        return cls(
            power=command.power,
            mode=command.mode,
            temperature=command.temperature,
            fan=command.fan,
            turbo=command.turbo,
            display=command.display,
            blow=command.blow,
            swing_v=command.swing_v,
            swing_h=command.swing_h,
        )

    def to_command(self) -> GreeAcCommand:
        """Build the frame carrying this state."""
        return GreeAcCommand(
            power=self.power,
            mode=self.mode,
            temperature=self.temperature,
            fan=self.fan,
            swing_v=self.swing_v,
            swing_h=self.swing_h,
            turbo=self.turbo,
            display=self.display,
            blow=self.blow,
        )


@dataclass
class GreeIrRuntimeData:
    """Runtime data for a Gree IR config entry.

    Holds the latest known state of the unit — the last frame sent to it, or the
    last one a configured receiver saw the remote send — shared by every entity of
    the entry so each one can build a full frame from it.
    """

    configured_modes: tuple[GreeAcMode, ...]
    ac_state: GreeAcState
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @callback
    def apply_received_command(self, command: GreeAcCommand) -> bool:
        """Record a frame the remote sent, reporting whether it addresses this unit.

        Kept here rather than on the climate entity because a frame the receiver
        picks up describes the whole unit, not only the part the climate entity
        shows.
        """
        state = GreeAcState.from_command(command)
        if command.mode not in self.configured_modes:
            if command.power:
                return False
            # Off frames carry a mode field too; one this entry may not send keeps
            # the mode the next power-off frame goes out with.
            state = replace(state, mode=self.ac_state.mode)

        # The remote's frame is now what the unit last saw, so a later frame has to
        # carry every field of it rather than the ones sent before it.
        self.ac_state = state
        return True


type GreeIrConfigEntry = ConfigEntry[GreeIrRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: GreeIrConfigEntry) -> bool:
    """Set up Gree IR from a config entry."""
    configured_modes = tuple(
        HA_MODE_TO_LIB[HVACMode(mode)]
        for mode in entry.data.get(CONF_HVAC_MODES, DEFAULT_HVAC_MODES)
    )
    entry.runtime_data = GreeIrRuntimeData(
        configured_modes=configured_modes,
        ac_state=GreeAcState(mode=configured_modes[0]),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreeIrConfigEntry) -> bool:
    """Unload a Gree IR config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
