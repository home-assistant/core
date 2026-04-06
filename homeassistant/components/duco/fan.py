"""Fan platform for the Duco integration."""

from __future__ import annotations

from typing import Any

from duco.exceptions import DucoError
from duco.models import Node, VentilationState

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

PARALLEL_UPDATES = 1

PRESET_AUTO = "auto"

# Permanent speed states ordered low → high.
ORDERED_NAMED_FAN_SPEEDS: list[VentilationState] = [
    VentilationState.CNT1,
    VentilationState.CNT2,
    VentilationState.CNT3,
]

_PRESET_TO_STATE: dict[str, VentilationState] = {
    PRESET_AUTO: VentilationState.AUTO,
}

_STATE_TO_PRESET: dict[VentilationState, str] = {
    VentilationState.AUTO: PRESET_AUTO,
    VentilationState.AUT1: PRESET_AUTO,
    VentilationState.AUT2: PRESET_AUTO,
    VentilationState.AUT3: PRESET_AUTO,
}

# Upper-bound percentages for 3 speed levels: 33 / 66 / 100.
# Using upper bounds guarantees that reading a percentage back and writing it
# again always round-trips to the same Duco state.
_SPEED_LEVEL_PERCENTAGES: list[int] = [
    (i + 1) * 100 // len(ORDERED_NAMED_FAN_SPEEDS)
    for i in range(len(ORDERED_NAMED_FAN_SPEEDS))
]

# Maps every active Duco state (including timed MAN variants) to its
# display percentage so externally-set timed modes show the correct level.
_STATE_TO_PERCENTAGE: dict[VentilationState, int] = {
    VentilationState.CNT1: _SPEED_LEVEL_PERCENTAGES[0],
    VentilationState.MAN1: _SPEED_LEVEL_PERCENTAGES[0],
    VentilationState.MAN1x2: _SPEED_LEVEL_PERCENTAGES[0],
    VentilationState.MAN1x3: _SPEED_LEVEL_PERCENTAGES[0],
    VentilationState.CNT2: _SPEED_LEVEL_PERCENTAGES[1],
    VentilationState.MAN2: _SPEED_LEVEL_PERCENTAGES[1],
    VentilationState.MAN2x2: _SPEED_LEVEL_PERCENTAGES[1],
    VentilationState.MAN2x3: _SPEED_LEVEL_PERCENTAGES[1],
    VentilationState.CNT3: _SPEED_LEVEL_PERCENTAGES[2],
    VentilationState.MAN3: _SPEED_LEVEL_PERCENTAGES[2],
    VentilationState.MAN3x2: _SPEED_LEVEL_PERCENTAGES[2],
    VentilationState.MAN3x3: _SPEED_LEVEL_PERCENTAGES[2],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco fan entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        DucoVentilationFanEntity(coordinator, node)
        for node in coordinator.data.values()
        if node.general.node_type == "BOX"
    )


class DucoVentilationFanEntity(DucoEntity, FanEntity):
    """Fan entity for the ventilation control of a Duco node."""

    _attr_translation_key = "manual_control"
    _attr_preset_modes = [PRESET_AUTO]
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)

    def __init__(self, coordinator: DucoCoordinator, node: Node) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, node)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{node.node_id}"

    @property
    def is_on(self) -> bool:
        """Return True; this device always ventilates and cannot be turned off."""
        return self._node.ventilation is not None

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage, or None when in a preset mode."""
        node = self._node
        if node.ventilation is None:
            return None
        return _STATE_TO_PERCENTAGE.get(node.ventilation.state)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, or None when a manual speed is active."""
        node = self._node
        if node.ventilation is None:
            return None
        return _STATE_TO_PRESET.get(node.ventilation.state)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed as a percentage (maps to low/medium/high)."""
        state = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        await self._async_set_state(state)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the ventilation preset mode."""
        self._valid_preset_mode_or_raise(preset_mode)
        await self._async_set_state(_PRESET_TO_STATE[preset_mode])

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on: set a specific speed/preset, or default to AUTO."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._async_set_state(VentilationState.AUTO)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off: hand control back to Duco (AUTO)."""
        await self._async_set_state(VentilationState.AUTO)

    async def _async_set_state(self, state: VentilationState) -> None:
        """Send the ventilation state to the device and refresh coordinator."""
        try:
            await self.coordinator.client.async_set_ventilation_state(
                self._node_id, state
            )
        except DucoError as err:
            raise HomeAssistantError(f"Failed to set ventilation state: {err}") from err
        await self.coordinator.async_refresh()
