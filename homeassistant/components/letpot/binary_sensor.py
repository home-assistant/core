"""Support for LetPot binary sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass

from letpot.models import DeviceFeature, LetPotDeviceStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LetPotConfigEntry, LetPotDeviceCoordinator
from .entity import LetPotEntity, LetPotEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LetPotBinarySensorEntityDescription(
    LetPotEntityDescription, BinarySensorEntityDescription
):
    """Describes a LetPot binary sensor entity."""

    is_on_fn: Callable[[LetPotDeviceStatus], bool]


BINARY_SENSORS: tuple[LetPotBinarySensorEntityDescription, ...] = (
    LetPotBinarySensorEntityDescription(
        key="low_nutrients",
        translation_key="low_nutrients",
        is_on_fn=lambda status: bool(status.errors.low_nutrients),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        supported_fn=(
            lambda coordinator: coordinator.data.errors.low_nutrients is not None
        ),
    ),
    LetPotBinarySensorEntityDescription(
        key="low_water",
        translation_key="low_water",
        is_on_fn=lambda status: bool(status.errors.low_water),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        supported_fn=lambda coordinator: coordinator.data.errors.low_water is not None,
    ),
    LetPotBinarySensorEntityDescription(
        key="pump",
        translation_key="pump",
        is_on_fn=lambda status: status.pump_status == 1,
        device_class=BinarySensorDeviceClass.RUNNING,
        supported_fn=(
            lambda coordinator: DeviceFeature.PUMP_STATUS
            in coordinator.device_client.device_features
        ),
    ),
    LetPotBinarySensorEntityDescription(
        key="pump_error",
        translation_key="pump_error",
        is_on_fn=lambda status: bool(status.errors.pump_malfunction),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        supported_fn=(
            lambda coordinator: coordinator.data.errors.pump_malfunction is not None
        ),
    ),
    LetPotBinarySensorEntityDescription(
        key="refill_error",
        translation_key="refill_error",
        is_on_fn=lambda status: bool(status.errors.refill_error),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        supported_fn=(
            lambda coordinator: coordinator.data.errors.refill_error is not None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LetPotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LetPot binary sensor entities based on a config entry and device status/features."""
    coordinators = entry.runtime_data
    async_add_entities(
        LetPotBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSORS
        for coordinator in coordinators
        if description.supported_fn(coordinator)
    )


class LetPotBinarySensorEntity(LetPotEntity, BinarySensorEntity):
    """Defines a LetPot binary sensor entity."""

    entity_description: LetPotBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: LetPotDeviceCoordinator,
        description: LetPotBinarySensorEntityDescription,
    ) -> None:
        """Initialize LetPot binary sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{coordinator.device.serial_number}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
