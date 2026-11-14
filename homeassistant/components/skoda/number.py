"""Support for Škoda number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, override

from skoda_public_api.api_layer.open_api_client import OpenAPIClient
from skoda_public_api.models.enums import VehicleCapability, VehicleOperationName

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import SkodaConfigEntry, SkodaUpdateCoordinator
from .entity import SkodaEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SkodaNumberEntityDescription(NumberEntityDescription):
    """Describes a Škoda number entity."""

    value_fn: Callable[[SkodaEntity], int | None]
    set_value_fn: Callable[[OpenAPIClient, str, int], Awaitable[Any]]
    required_capabilities: frozenset[VehicleCapability]
    required_operations: frozenset[VehicleOperationName]

    def is_supported(
        self,
        capabilities: set[VehicleCapability],
        operations: set[VehicleOperationName] | None,
    ) -> bool:
        """Return whether the vehicle supports this number entity.

        The operations list can be temporarily unavailable, in which case only
        the capabilities are checked so a transient error does not hide the entity.
        """
        if not self.required_capabilities <= capabilities:
            return False
        return operations is None or self.required_operations <= operations


def _charge_limit_value(entity: SkodaEntity) -> int | None:
    charging = entity.open_api_charging
    if not charging or not charging.settings:
        return None
    return charging.settings.target_state_of_charge_in_percent


NUMBER_TYPES: tuple[SkodaNumberEntityDescription, ...] = (
    SkodaNumberEntityDescription(
        key="charge_limit",
        translation_key="charge_limit",
        device_class=NumberDeviceClass.BATTERY,
        entity_category=EntityCategory.CONFIG,
        native_min_value=50,
        native_max_value=100,
        native_step=10,
        native_unit_of_measurement=PERCENTAGE,
        required_capabilities=frozenset({VehicleCapability.CHARGING}),
        required_operations=frozenset({VehicleOperationName.SET_CHARGING_LIMIT}),
        value_fn=_charge_limit_value,
        set_value_fn=lambda client, vin, value: client.set_charge_limit(vin, value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Škoda number entities from ConfigEntry runtime_data."""
    coordinator = entry.runtime_data.coordinator
    vehicle_response = coordinator.data.vehicle_response
    capabilities = vehicle_response.supported_capabilities()
    operations = vehicle_response.supported_operations()

    async_add_entities(
        SkodaNumber(coordinator, description)
        for description in NUMBER_TYPES
        if description.is_supported(capabilities, operations)
    )


class SkodaNumber(SkodaEntity, NumberEntity):
    """Škoda number entity, driven by its entity description."""

    entity_description: SkodaNumberEntityDescription

    def __init__(
        self,
        coordinator: SkodaUpdateCoordinator,
        description: SkodaNumberEntityDescription,
    ) -> None:
        """Initialize the number entity with a coordinator and its entity description."""
        self.entity_description = description
        super().__init__(coordinator, coordinator.vin)
        self._attr_native_value = description.value_fn(self)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update the value from the latest vehicle data."""
        self._attr_native_value = self.entity_description.value_fn(self)
        super()._handle_coordinator_update()

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Send the new value to the vehicle."""
        # number.set_value only validates the range, not the step.
        if value % self.step:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_step",
                translation_placeholders={
                    "value": f"{value:g}",
                    "step": f"{self.step:g}",
                },
            )
        native_value = round(value)
        await self.async_send_command(
            self.entity_description.set_value_fn(
                self.coordinator.openapi, self.vin, native_value
            )
        )
        self._attr_native_value = native_value
        self.async_write_ha_state()
