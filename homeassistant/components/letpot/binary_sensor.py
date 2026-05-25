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

from .coordinator import LetPotConfigEntry, LetPotDeviceCoordinator, LetPotGardenStatus
from .entity import LetPotEntity, LetPotEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LetPotBinarySensorEntityDescription[_DataT: LetPotDeviceStatus](
    LetPotEntityDescription, BinarySensorEntityDescription
):
    """Describes a LetPot binary sensor entity."""

    is_on_fn: Callable[[_DataT], bool]


BINARY_SENSORS: tuple[LetPotBinarySensorEntityDescription[LetPotGardenStatus], ...] = (
    LetPotBinarySensorEntityDescription[LetPotGardenStatus](
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
    LetPotBinarySensorEntityDescription[LetPotGardenStatus](
        key="low_water",
        translation_key="low_water",
        is_on_fn=lambda status: bool(status.errors.low_water),
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=BinarySensorDeviceClass.PROBLEM,
        supported_fn=lambda coordinator: coordinator.data.errors.low_water is not None,
    ),
    LetPotBinarySensorEntityDescription[LetPotGardenStatus](
        key="pump",
        translation_key="pump",
        is_on_fn=lambda status: status.pump_status == 1,
        device_class=BinarySensorDeviceClass.RUNNING,
        supported_fn=(
            lambda coordinator: (
                DeviceFeature.PUMP_STATUS
                in coordinator.device_client.device_info(
                    coordinator.device.serial_number
                ).features
            )
        ),
    ),
    LetPotBinarySensorEntityDescription[LetPotGardenStatus](
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
    LetPotBinarySensorEntityDescription[LetPotGardenStatus](
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
    """Set up LetPot binary sensor entities."""
    coordinators = entry.runtime_data
    async_add_entities(
        LetPotBinarySensorEntity[LetPotGardenStatus](coordinator, description)
        for description in BINARY_SENSORS
        for coordinator in coordinators
        if description.supported_fn(coordinator)
    )


class LetPotBinarySensorEntity[_DataT: LetPotDeviceStatus](
    LetPotEntity[_DataT], BinarySensorEntity
):
    """Defines a LetPot binary sensor entity."""

    entity_description: LetPotBinarySensorEntityDescription[_DataT]

    def __init__(
        self,
        coordinator: LetPotDeviceCoordinator[_DataT],
        description: LetPotBinarySensorEntityDescription[_DataT],
    ) -> None:
        """Initialize LetPot binary sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id}"
            f"_{coordinator.device.serial_number}"
            f"_{description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
