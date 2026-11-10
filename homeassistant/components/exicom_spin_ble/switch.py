"""Switches for the Spin EV Charger integration."""

from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SpinEvConfigEntry
from .entity import SpinEvEntity

PARALLEL_UPDATES = 1

CHARGING_DESCRIPTION = SwitchEntityDescription(
    key="charging",
    translation_key="charging",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpinEvConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the charger switches."""
    async_add_entities([SpinEvChargingSwitch(entry.runtime_data, CHARGING_DESCRIPTION)])


class SpinEvChargingSwitch(SpinEvEntity, SwitchEntity):
    """Start and stop charging."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True while a session is open."""
        state = self.coordinator.data.state
        if state is None:
            return None
        # A vehicle pausing resumes without a command, so a suspended session
        # stays on rather than flapping mid-charge.
        return state.is_charging or state.is_suspended

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging."""
        await self.coordinator.async_start_charging()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging."""
        await self.coordinator.async_stop_charging()
