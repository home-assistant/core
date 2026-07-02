"""Support for Velux exterior heating number entities."""

from dataclasses import replace
from typing import override

from pyvlx import ExteriorHeating, Intensity, OpeningDevice, Position

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import VeluxConfigEntry
from .const import DOMAIN
from .coordinator import VeluxLimitationCoordinator
from .entity import (
    VeluxEntity,
    velux_device_info,
    velux_unique_id,
    wrap_pyvlx_call_exceptions,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities for the Velux platform."""
    pyvlx = config_entry.runtime_data.pyvlx
    limitation_coordinators = config_entry.runtime_data.limitation_coordinators
    entities: list[NumberEntity] = [
        VeluxExteriorHeatingNumber(node, config_entry.entry_id)
        for node in pyvlx.nodes
        if isinstance(node, ExteriorHeating)
    ]
    for node in pyvlx.nodes:
        if isinstance(node, OpeningDevice):
            coordinator = limitation_coordinators[node.node_id]
            entities.extend(
                [
                    VeluxOpenPositionLimitNumber(coordinator, config_entry.entry_id),
                    VeluxClosedPositionLimitNumber(coordinator, config_entry.entry_id),
                ]
            )
    async_add_entities(entities)


class VeluxExteriorHeatingNumber(VeluxEntity, NumberEntity):
    """Representation of an exterior heating intensity control."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_name = None

    node: ExteriorHeating

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current heating intensity in percent."""
        return (
            self.node.intensity.intensity_percent if self.node.intensity.known else None
        )

    @wrap_pyvlx_call_exceptions
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the heating intensity."""
        await self.node.set_intensity(
            Intensity(intensity_percent=round(value)),
            wait_for_completion=True,
        )


class VeluxPositionLimitNumber(
    CoordinatorEntity[VeluxLimitationCoordinator], NumberEntity
):
    """Shared behavior for Velux limitation number entities.

    Home Assistant expresses cover position as opening percentage, while pyvlx
    uses the opposite direction. These entities expose HA-side open/closed
    position limits and convert to pyvlx positions only at the API boundary.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True

    _limitation_kind: str

    def __init__(
        self, coordinator: VeluxLimitationCoordinator, config_entry_id: str
    ) -> None:
        """Initialize Velux limitation number."""
        CoordinatorEntity.__init__(self, coordinator)
        node = coordinator.node
        unique_id = velux_unique_id(node, config_entry_id)
        self._attr_unique_id = f"{unique_id}_{self._limitation_kind}_limitation"
        self._attr_translation_key = f"{self._limitation_kind}_position_limitation"
        self._attr_device_info = velux_device_info(node, config_entry_id)

    @override
    async def async_added_to_hass(self) -> None:
        """Request an immediate refresh when the entity is first added."""
        await super().async_added_to_hass()
        # Request an immediate refresh if we haven't fetched data yet
        if self.coordinator.data is None:
            await self.coordinator.async_request_refresh()

    @property
    @override
    def available(self) -> bool:
        """Return False until coordinator has successfully populated data.

        The entity is only available once the coordinator has successfully
        fetched data at least once.
        """
        if self.coordinator.data is None:
            return False
        return super().available

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current limitation in Home Assistant semantics."""
        if position := self._get_pyvlx_limit():
            return 100 - position.position_percent
        return None

    @wrap_pyvlx_call_exceptions
    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the limitation in Home Assistant semantics."""
        if self.coordinator.data is None:
            await self.coordinator.async_refresh()

        if self.coordinator.data is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_limitation_before_data",
            )

        if self._overlaps(value):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="limitation_overlap",
            )

        await self._async_set_pyvlx_limitation(
            Position(position_percent=100 - round(value))
        )

    def _get_pyvlx_limit(self) -> Position | None:
        """Get the pyvlx limitation backing this HA-side entity."""
        raise NotImplementedError

    def _updated_pyvlx_limits(
        self, updated_position: Position, current_min: Position, current_max: Position
    ) -> tuple[Position, Position]:
        """Return pyvlx min/max values with this entity's side updated."""
        raise NotImplementedError

    async def _async_set_pyvlx_limitation(self, position: Position) -> None:
        """Set pyvlx limitations while preserving the unchanged side."""
        assert self.coordinator.data is not None  # checked in async_set_native_value
        current_min = self.coordinator.data.limitation_min
        current_max = self.coordinator.data.limitation_max
        position_min, position_max = self._updated_pyvlx_limits(
            position, current_min, current_max
        )
        await self.coordinator.node.set_position_limitations(
            position_min=position_min,
            position_max=position_max,
        )
        self.coordinator.async_set_updated_data(
            replace(
                self.coordinator.data,
                limitation_min=position_min,
                limitation_max=position_max,
            )
        )

    def _overlaps(self, value: float) -> bool:
        """Check if a value would overlap with sibling limitation."""
        raise NotImplementedError


class VeluxClosedPositionLimitNumber(VeluxPositionLimitNumber):
    """Representation of the closed position limit."""

    _attr_native_min_value = 0
    _limitation_kind = "closed"

    def _sibling_value(self) -> float | None:
        """Return the sibling open limit value, or None if unknown."""
        return (
            100 - self.coordinator.data.limitation_min.position_percent
            if self.coordinator.data
            else None
        )

    @property
    @override
    def native_max_value(self) -> float:
        """Return the upper bound: the current open limit (or 100 if unknown)."""
        sibling_value = self._sibling_value()
        return sibling_value if sibling_value is not None else 100

    @override
    def _get_pyvlx_limit(self) -> Position | None:
        """Get the pyvlx max limit backing the HA closed position limit."""
        return self.coordinator.data.limitation_max if self.coordinator.data else None

    @override
    def _updated_pyvlx_limits(
        self, updated_position: Position, current_min: Position, current_max: Position
    ) -> tuple[Position, Position]:
        """Update pyvlx max and preserve pyvlx min for HA closed limit changes."""
        return current_min, updated_position

    @override
    def _overlaps(self, value: float) -> bool:
        """Check if the closed limit would overlap the open limit."""
        sibling_value = self._sibling_value()
        return sibling_value is not None and value > sibling_value


class VeluxOpenPositionLimitNumber(VeluxPositionLimitNumber):
    """Representation of the open position limit."""

    _attr_native_max_value = 100
    _limitation_kind = "open"

    def _sibling_value(self) -> float | None:
        """Return the sibling close limit value, or None if unknown."""
        return (
            100 - self.coordinator.data.limitation_max.position_percent
            if self.coordinator.data
            else None
        )

    @property
    @override
    def native_min_value(self) -> float:
        """Return the lower bound: the current closed limit (or 0 if unknown)."""
        sibling_value = self._sibling_value()
        return sibling_value if sibling_value is not None else 0

    @override
    def _get_pyvlx_limit(self) -> Position | None:
        """Get the pyvlx min limit backing the HA open position limit."""
        return self.coordinator.data.limitation_min if self.coordinator.data else None

    @override
    def _updated_pyvlx_limits(
        self, updated_position: Position, current_min: Position, current_max: Position
    ) -> tuple[Position, Position]:
        """Update pyvlx min and preserve pyvlx max for HA open limit changes."""
        return updated_position, current_max

    @override
    def _overlaps(self, value: float) -> bool:
        """Check if the open limit would overlap the closed limit."""
        sibling_value = self._sibling_value()
        return sibling_value is not None and value < sibling_value
