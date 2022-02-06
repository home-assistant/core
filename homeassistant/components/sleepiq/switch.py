"""Support for SleepIQ switches."""
from __future__ import annotations

from datetime import timedelta
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle

from .const import DOMAIN, SLEEPIQ_DATA
from .device import SleepNumberEntity

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sleep number switches."""
    data = hass.data[DOMAIN][config_entry.entry_id][SLEEPIQ_DATA]

    entities: list[SleepNumberPrivateSwitch] = []
    for bed in data.beds.values():
        entities.append(SleepNumberPrivateSwitch(bed))

    async_add_entities(entities)


class SleepNumberPrivateSwitch(SleepNumberEntity, SwitchEntity):
    """Representation of an SleepIQ privacy mode."""

    def __init__(self, bed):
        super().__init__(bed)
        self._attr_name = f"{bed.name} Pause Mode"
        self._attr_unique_id = f"{bed.id}-PauseMode"

    @property
    def is_on(self) -> bool:
        """Return whether the switch is on or off."""
        return self._bed.paused

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        await self._bed.set_pause_mode(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        await self._bed.set_pause_mode(False)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self, **kwargs) -> None:
        """Get the latest data from the SleepIQ API."""
        await self._bed.fetch_pause_mode()
