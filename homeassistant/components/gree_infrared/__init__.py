"""Gree IR Remote integration for Home Assistant."""

from dataclasses import dataclass, field
from typing import Self

from infrared_protocols.commands.gree_ac import (
    MIN_TEMP,
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]


@dataclass(frozen=True, kw_only=True)
class GreeAcState:
    """The state a Gree frame carries.

    Every frame carries the whole state, so an entity changing one field has to
    resend the fields the other entities own.
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

    Holds the state last sent to the unit, shared by every entity of the entry so
    each one can build a full frame from it.
    """

    ac_state: GreeAcState = field(default_factory=GreeAcState)


type GreeIrConfigEntry = ConfigEntry[GreeIrRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: GreeIrConfigEntry) -> bool:
    """Set up Gree IR from a config entry."""
    entry.runtime_data = GreeIrRuntimeData()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreeIrConfigEntry) -> bool:
    """Unload a Gree IR config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
