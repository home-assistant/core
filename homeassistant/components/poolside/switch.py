"""Switch platform for Poolside on/off-only controls."""

from typing import Any, override

from aiopoolside import PoolsideClient, PoolsideControl
from aiopoolside.const import StatusState

from homeassistant.components.switch import SwitchEntity
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
    """Set up Poolside switch entities.

    Water features/cleaners/filters/blowers that report a single
    SpeedIncrements value are plain on/off, unlike their variable-speed
    siblings exposed by the fan platform. BLOWER is always on/off (it has no
    SpeedIncrements at all). UNKNOWN control types (a type this integration
    doesn't yet classify) are also rendered as a plain switch driven by
    Status, ignoring any other fields.
    """
    data = entry.runtime_data
    async_add_entities(
        PoolsideSwitch(data.client, control)
        for control in data.controls
        if control_platform(control) is Platform.SWITCH
    )


class PoolsideSwitch(PoolsideEntity, SwitchEntity):
    """An on/off-only water feature, cleaner, filter, blower, or unknown control."""

    def __init__(self, client: PoolsideClient, control: PoolsideControl) -> None:
        """Set up the switch for a given control."""
        super().__init__(client, control)
        if icon_key := ICON_TRANSLATION_KEYS.get(control.control_type):
            self._attr_translation_key = icon_key

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the control is on."""
        status = self._power_state()
        if status is None:
            return None
        return status == StatusState.ON

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the control on."""
        await self._async_write_state(Status=StatusState.ON.value)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the control off."""
        await self._async_write_state(Status=StatusState.OFF.value)
