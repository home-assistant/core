"""Fan platform for the Novy Hood."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .commands import NovyHoodMinus, NovyHoodPlus
from .entity import NovyHoodEntity

PARALLEL_UPDATES = 1

SPEED_COUNT = 4
STEP_GAP = 0.1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Novy Hood fan platform."""
    async_add_entities([NovyHoodFan(config_entry)])


class NovyHoodFan(NovyHoodEntity, FanEntity, RestoreEntity):
    """Novy hood fan controlled via +/- RF presses."""

    _attr_assumed_state = True
    _attr_name = None
    _attr_should_poll = False
    _attr_speed_count = SPEED_COUNT
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the fan."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_fan"
        self._level = 0

    @property
    def percentage(self) -> int:
        """Return the current assumed percentage."""
        return self._level * 25

    @property
    def is_on(self) -> bool:
        """Return whether the fan is currently on."""
        return self._level > 0

    async def async_added_to_hass(self) -> None:
        """Restore last-known level from saved percentage."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        stored = last_state.attributes.get("percentage")
        if stored is None:
            return
        self._level = max(0, min(SPEED_COUNT, round(stored / 25)))

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if self._level == 0:
            await self._async_send(NovyHoodPlus())
            self._level = 1
            self.async_write_ha_state()
        if percentage is not None:
            await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off by sending `minus` four times."""
        await self._async_send_repeated(NovyHoodMinus, SPEED_COUNT, STEP_GAP)
        self._level = 0
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Walk the assumed level to match the target percentage."""
        target = max(0, min(SPEED_COUNT, round(percentage / 25)))
        if target == 0:
            await self.async_turn_off()
            return
        delta = target - self._level
        if delta > 0:
            await self._async_send_repeated(NovyHoodPlus, delta, STEP_GAP)
        elif delta < 0:
            await self._async_send_repeated(NovyHoodMinus, -delta, STEP_GAP)
        self._level = target
        self.async_write_ha_state()
