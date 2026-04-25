"""Switch platform for NRGkick."""

from __future__ import annotations

from typing import Any

from nrgkick_api.const import CONTROL_KEY_CHARGE_PAUSE

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NRGkickConfigEntry, NRGkickData, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

PARALLEL_UPDATES = 0

CHARGING_ENABLED_KEY = "charging_enabled"


def _is_charging_enabled(data: NRGkickData) -> bool:
    """Return True if charging is enabled (not paused)."""
    return bool(data.control.get(CONTROL_KEY_CHARGE_PAUSE) == 0)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: NRGkickConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up NRGkick switches based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities([NRGkickChargingEnabledSwitch(coordinator)])


class NRGkickChargingEnabledSwitch(NRGkickEntity, SwitchEntity):
    """Representation of the NRGkick charging enabled switch."""

    _attr_translation_key = CHARGING_ENABLED_KEY

    def __init__(self, coordinator: NRGkickDataUpdateCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, CHARGING_ENABLED_KEY)

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        data = self.coordinator.data
        assert data is not None
        return _is_charging_enabled(data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on (enable charging)."""
        await self._async_call_api(self.coordinator.api.set_charge_pause(False))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off (pause charging)."""
        await self._async_call_api(self.coordinator.api.set_charge_pause(True))
