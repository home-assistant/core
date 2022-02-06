"""Support for SleepIQ switches."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR
from .device import SleepNumberEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sleep number switches."""
    data = hass.data[DOMAIN][config_entry.entry_id][SLEEPIQ_DATA]
    status_coordinator = hass.data[DOMAIN][config_entry.entry_id][
        SLEEPIQ_STATUS_COORDINATOR
    ]

    entities: list[SleepNumberPrivateSwitch] = []
    for bed in data.beds.values():
        entities.append(SleepNumberPrivateSwitch(bed, status_coordinator))

    async_add_entities(entities)


class SleepNumberPrivateSwitch(SleepNumberEntity, SwitchEntity):
    """Representation of an SleepIQ privacy mode."""

    def __init__(self, bed, status_coordinator):
        super().__init__(bed, status_coordinator)
        self._attr_name = f"{bed.name} Pause Mode"
        self._attr_unique_id = f"{bed.id}-PauseMode"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on or off."""
        return self._bed.paused

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        await self._bed.set_pause_mode(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        await self._bed.set_pause_mode(True)
        self.async_write_ha_state()
