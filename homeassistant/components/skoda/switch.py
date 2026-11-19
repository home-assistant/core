"""Support for Škoda switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from skoda_public_api.api_layer.open_api_client import OpenAPIClient
from skoda_public_api.models.enums import (
    ChargingState,
    VehicleCapability,
    VehicleOperationName,
    VentilationState,
)

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaUpdateCoordinator
from .entity import SkodaEntity

PARALLEL_UPDATES = 1

_VENTILATION_STATE_MAP = {
    VentilationState.OFF: False,
    VentilationState.PREHEATING: True,
    VentilationState.VENTILATION: True,
}


@dataclass(frozen=True, kw_only=True)
class SkodaSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Škoda switch entity."""

    is_on_fn: Callable[[SkodaEntity], bool | None]
    turn_on_fn: Callable[[OpenAPIClient, str], Awaitable[Any]]
    turn_off_fn: Callable[[OpenAPIClient, str], Awaitable[Any]]
    required_capabilities: frozenset[VehicleCapability]
    required_operations: frozenset[VehicleOperationName]

    def is_supported(
        self,
        capabilities: set[VehicleCapability],
        operations: set[VehicleOperationName] | None,
    ) -> bool:
        """Return whether the vehicle supports this switch.

        The operations list can be temporarily unavailable, in which case only
        the capabilities are checked so a transient error does not hide the switch.
        """
        if not self.required_capabilities <= capabilities:
            return False
        return operations is None or self.required_operations <= operations


def _charging_value(entity: SkodaEntity) -> bool | None:
    charging = entity.open_api_charging
    if not charging or not charging.status:
        return None
    if charging.status.state in (None, ChargingState.UNKNOWN):
        return None
    return charging.status.state == ChargingState.CHARGING


def _active_ventilation_value(entity: SkodaEntity) -> bool | None:
    active_ventilation = entity.open_api_active_ventilation
    if active_ventilation is None:
        return None
    return _VENTILATION_STATE_MAP.get(active_ventilation.state)


SWITCH_TYPES: tuple[SkodaSwitchEntityDescription, ...] = (
    SkodaSwitchEntityDescription(
        key="charging",
        translation_key="charging",
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        required_operations=frozenset(
            {VehicleOperationName.START_CHARGING, VehicleOperationName.STOP_CHARGING}
        ),
        is_on_fn=_charging_value,
        turn_on_fn=lambda client, vin: client.start_charging(vin),
        turn_off_fn=lambda client, vin: client.stop_charging(vin),
    ),
    SkodaSwitchEntityDescription(
        key="active_ventilation",
        translation_key="active_ventilation",
        required_capabilities=frozenset({VehicleCapability.ACTIVE_VENTILATION}),
        required_operations=frozenset(
            {
                VehicleOperationName.START_ACTIVE_VENTILATION,
                VehicleOperationName.STOP_ACTIVE_VENTILATION,
            }
        ),
        is_on_fn=_active_ventilation_value,
        turn_on_fn=lambda client, vin: client.start_active_ventilation(vin),
        turn_off_fn=lambda client, vin: client.stop_active_ventilation(vin),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda switches from ConfigEntry runtime_data."""
    coordinator = entry.runtime_data.coordinator
    vehicle_response = coordinator.data.vehicle_response
    capabilities = vehicle_response.supported_capabilities()
    operations = vehicle_response.supported_operations()

    async_add_entities(
        SkodaSwitch(coordinator, description)
        for description in SWITCH_TYPES
        if description.is_supported(capabilities, operations)
    )


class SkodaSwitch(SkodaEntity, SwitchEntity):
    """Škoda switch entity, driven by its entity description."""

    entity_description: SkodaSwitchEntityDescription

    def __init__(
        self,
        coordinator: SkodaUpdateCoordinator,
        description: SkodaSwitchEntityDescription,
    ) -> None:
        """Initialize the switch with a coordinator and its entity description."""
        self.entity_description = description
        super().__init__(coordinator, coordinator.vin)
        self._attr_is_on = description.is_on_fn(self)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update the switch state from the latest vehicle data."""
        self._attr_is_on = self.entity_description.is_on_fn(self)
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.async_send_command(
            self.entity_description.turn_on_fn(self.coordinator.openapi, self.vin)
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.async_send_command(
            self.entity_description.turn_off_fn(self.coordinator.openapi, self.vin)
        )
        self._attr_is_on = False
        self.async_write_ha_state()
