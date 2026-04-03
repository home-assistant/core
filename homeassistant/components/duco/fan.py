"""Fan platform for the Duco integration."""

from __future__ import annotations

from typing import Any

from duco.exceptions import DucoError
from duco.models import Node, VentilationState

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

PARALLEL_UPDATES = 0

PRESET_AUTO = "auto"
PRESET_AWAY = "away"
PRESET_LOW = "low"
PRESET_LOW_FORCED = "low_forced"
PRESET_MEDIUM = "medium"
PRESET_MEDIUM_FORCED = "medium_forced"
PRESET_HIGH = "high"
PRESET_HIGH_FORCED = "high_forced"

_PRESET_TO_STATE: dict[str, VentilationState] = {
    PRESET_AUTO: VentilationState.AUTO,
    PRESET_AWAY: VentilationState.EMPT,
    PRESET_LOW: VentilationState.MAN1,
    PRESET_LOW_FORCED: VentilationState.CNT1,
    PRESET_MEDIUM: VentilationState.MAN2,
    PRESET_MEDIUM_FORCED: VentilationState.CNT2,
    PRESET_HIGH: VentilationState.MAN3,
    PRESET_HIGH_FORCED: VentilationState.CNT3,
}

_STATE_TO_PRESET: dict[VentilationState, str] = {
    VentilationState.AUTO: PRESET_AUTO,
    VentilationState.AUT1: PRESET_AUTO,
    VentilationState.AUT2: PRESET_AUTO,
    VentilationState.AUT3: PRESET_AUTO,
    VentilationState.EMPT: PRESET_AWAY,
    VentilationState.MAN1: PRESET_LOW,
    VentilationState.MAN1x2: PRESET_LOW,
    VentilationState.MAN1x3: PRESET_LOW,
    VentilationState.CNT1: PRESET_LOW_FORCED,
    VentilationState.MAN2: PRESET_MEDIUM,
    VentilationState.MAN2x2: PRESET_MEDIUM,
    VentilationState.MAN2x3: PRESET_MEDIUM,
    VentilationState.CNT2: PRESET_MEDIUM_FORCED,
    VentilationState.MAN3: PRESET_HIGH,
    VentilationState.MAN3x2: PRESET_HIGH,
    VentilationState.MAN3x3: PRESET_HIGH,
    VentilationState.CNT3: PRESET_HIGH_FORCED,
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
        for node in coordinator.data
        if node.ventilation is not None
    )


class DucoVentilationFanEntity(DucoEntity, FanEntity):
    """Fan entity for the ventilation control of a Duco node."""

    _attr_translation_key = "ventilation"
    _attr_preset_modes = [
        PRESET_AUTO,
        PRESET_AWAY,
        PRESET_LOW,
        PRESET_LOW_FORCED,
        PRESET_MEDIUM,
        PRESET_MEDIUM_FORCED,
        PRESET_HIGH,
        PRESET_HIGH_FORCED,
    ]
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: DucoCoordinator, node: Node) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, node)
        mac = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{mac}_{node.node_id}_ventilation"

    @property
    def is_on(self) -> bool:
        """Return True always; the fan is always running physically."""
        return True

    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state on coordinator update."""
        self._attr_preset_mode = None
        super()._handle_coordinator_update()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self._attr_preset_mode is not None:
            return self._attr_preset_mode
        node = self._node
        if node is None or node.ventilation is None:
            return None
        return _STATE_TO_PRESET.get(node.ventilation.state)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the ventilation preset mode."""
        if preset_mode not in _PRESET_TO_STATE:
            raise ServiceValidationError(f"Invalid preset mode: {preset_mode}")
        # Optimistically update the UI immediately.
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
        await self._async_set_state(_PRESET_TO_STATE[preset_mode])

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Switch to manual ventilation (default: medium)."""
        target = preset_mode or PRESET_MEDIUM
        if target not in _PRESET_TO_STATE:
            raise ServiceValidationError(f"Invalid preset mode: {target}")
        self._attr_preset_mode = target
        self.async_write_ha_state()
        await self._async_set_state(_PRESET_TO_STATE[target])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Return to automatic ventilation control."""
        self._attr_preset_mode = PRESET_AUTO
        self.async_write_ha_state()
        await self._async_set_state(VentilationState.AUTO)

    async def _async_set_state(self, state: VentilationState) -> None:
        """Send the ventilation state to the device and refresh coordinator."""
        try:
            await self.coordinator.client.async_set_ventilation_state(
                self._node_id, state
            )
        except DucoError as err:
            # Revert optimistic state on failure.
            self._attr_preset_mode = None
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to set ventilation state: {err}") from err
        await self.coordinator.async_request_refresh()
