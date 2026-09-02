"""Binary sensor platform for the Duco integration."""

from dataclasses import dataclass
from typing import override

from duco_connectivity.models import DiagStatus, Node

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BOX_NODE_ID
from .coordinator import DucoConfigEntry, DucoCoordinator
from .entity import DucoEntity

PARALLEL_UPDATES = 0

DIAGNOSTIC_STATUS_TO_PROBLEM = {
    DiagStatus.DISABLED: True,
    DiagStatus.ERROR: True,
    DiagStatus.OK: False,
}


@dataclass(frozen=True, kw_only=True)
class DucoDiagnosticBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Duco diagnostic subsystem binary sensor."""

    component: str


# Ventilation and filter problems are directly actionable. Model-specific
# subsystem diagnostics remain opt-in.
DIAGNOSTIC_BINARY_SENSOR_DESCRIPTIONS: dict[
    str, DucoDiagnosticBinarySensorEntityDescription
] = {
    "Filter": DucoDiagnosticBinarySensorEntityDescription(
        key="filter",
        component="Filter",
        translation_key="diagnostic_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "SunCtrl": DucoDiagnosticBinarySensorEntityDescription(
        key="sun_control",
        component="SunCtrl",
        translation_key="diagnostic_sun_control",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "VentCool": DucoDiagnosticBinarySensorEntityDescription(
        key="ventilation_cooling",
        component="VentCool",
        translation_key="diagnostic_ventilation_cooling",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    "Ventilation": DucoDiagnosticBinarySensorEntityDescription(
        key="ventilation",
        component="Ventilation",
        translation_key="diagnostic_ventilation",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DucoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duco diagnostic binary sensors."""
    coordinator = entry.runtime_data
    known_components: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add newly reported diagnostic subsystems."""
        if (box_node := coordinator.data.nodes.get(BOX_NODE_ID)) is None:
            return

        new_entities: list[DucoDiagnosticBinarySensorEntity] = []
        for component in coordinator.data.diagnostic_subsystems:
            if component in known_components:
                continue
            # Only expose components whose problem semantics are confirmed.
            if (
                description := DIAGNOSTIC_BINARY_SENSOR_DESCRIPTIONS.get(component)
            ) is None:
                continue
            known_components.add(component)
            new_entities.append(
                DucoDiagnosticBinarySensorEntity(coordinator, box_node, description)
            )

        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class DucoDiagnosticBinarySensorEntity(DucoEntity, BinarySensorEntity):
    """Binary sensor for a Duco diagnostic subsystem."""

    entity_description: DucoDiagnosticBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: DucoCoordinator,
        node: Node,
        description: DucoDiagnosticBinarySensorEntityDescription,
    ) -> None:
        """Initialize the diagnostic binary sensor."""
        self.entity_description = description
        super().__init__(coordinator, node)
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{node.node_id}_{description.component}_diagnostic"

    @property
    @override
    def available(self) -> bool:
        """Return whether current diagnostic data is available."""
        return super().available and self.coordinator.data.diagnostics_available

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the diagnostic subsystem reports a problem."""
        if (
            status := self.coordinator.data.diagnostic_subsystems.get(
                self.entity_description.component
            )
        ) is None:
            return None
        return DIAGNOSTIC_STATUS_TO_PROBLEM.get(status)
