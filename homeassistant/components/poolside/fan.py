"""Fan platform for Poolside variable-speed controls (water features, cleaners, filters)."""

from typing import Any, override

from aiopoolside import PoolsideClient, PoolsideControl
from aiopoolside.const import POWER_LEVEL_FIELD, StatusState

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PoolsideConfigEntry
from .const import ICON_TRANSLATION_KEYS
from .entity import PoolsideEntity, control_platform


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PoolsideConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Poolside fan entities (variable-speed water features/pumps)."""
    data = entry.runtime_data
    async_add_entities(
        PoolsideFan(data.client, control)
        for control in data.controls
        if control_platform(control) is Platform.FAN
    )


class PoolsideFan(PoolsideEntity, FanEntity):
    """A variable-speed control exposed as a fan with a fixed set of speed steps."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the fan, reading its allowed speed percentages from the control."""
        super().__init__(client, control)
        if icon_key := ICON_TRANSLATION_KEYS.get(control.control_type):
            self._attr_translation_key = icon_key
        self._speed_increments = control.speed_increments
        self._attr_speed_count = len(self._speed_increments)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the control is on."""
        status = self._power_state()
        if status is None:
            return None
        return status == StatusState.ON

    @property
    @override
    def percentage(self) -> int | None:
        """Return the control's current output level."""
        value = self._desired(POWER_LEVEL_FIELD)
        if value is None:
            return None
        return round(float(value))

    def _nearest_increment(self, requested: int) -> int:
        """Round a requested percentage to the closest speed this control supports."""
        return min(self._speed_increments, key=lambda step: abs(step - requested))

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the control's output level, snapping to the nearest supported step."""
        if percentage == 0:
            await self._async_write_state(Status=StatusState.OFF.value)
            return
        power_level = self._nearest_increment(percentage)
        await self._async_write_state(
            Status=StatusState.ON.value, PowerLevel=str(power_level)
        )

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the control on, optionally at a given output level."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
            return
        await self._async_write_state(Status=StatusState.ON.value)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the control off."""
        await self._async_write_state(Status=StatusState.OFF.value)
