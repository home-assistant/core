"""Support for Roborock sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from roborock.data import CleanFluidStatus, RoborockStateCode
from roborock.data.v1.v1_containers import StatusField, StatusV2
from roborock.devices.traits.v1 import PropertiesApi
from roborock.roborock_message import RoborockZeoProtocol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    RoborockConfigEntry,
    RoborockCoordinatorType,
    RoborockDataUpdateCoordinator,
    RoborockDataUpdateCoordinatorA01,
    RoborockWashingMachineUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityA01, RoborockCoordinatedEntityV1
from .models import DeviceState

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RoborockBinarySensorDescription(BinarySensorEntityDescription):
    """A class that describes Roborock binary sensors."""

    value_fn: Callable[[DeviceState], bool | int | None]
    """A function that extracts the sensor value from DeviceState."""

    is_dock_entity: bool = False
    """Whether this sensor is for the dock."""

    support_fn: Callable[[PropertiesApi], bool] = lambda _: True
    """Function to determine if binary sensor is supported by the device."""


@dataclass(frozen=True, kw_only=True)
class RoborockBinarySensorDescriptionA01(BinarySensorEntityDescription):
    """A class that describes Roborock A01 binary sensors."""

    data_protocol: RoborockZeoProtocol
    value_fn: Callable[[StateType], bool]


BINARY_SENSOR_DESCRIPTIONS = [
    RoborockBinarySensorDescription(
        key="dry_status",
        translation_key="mop_drying_status",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.dry_status,
        is_dock_entity=True,
        support_fn=lambda api: api.device_features.is_field_supported(
            StatusV2, StatusField.DRY_STATUS
        ),
    ),
    RoborockBinarySensorDescription(
        key="water_box_carriage_status",
        translation_key="mop_attached",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_box_carriage_status,
        support_fn=lambda api: api.device_features.is_support_water_mode,
    ),
    RoborockBinarySensorDescription(
        key="water_box_status",
        translation_key="water_box_attached",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_box_status,
        support_fn=lambda api: api.device_features.is_support_water_mode,
    ),
    RoborockBinarySensorDescription(
        key="water_shortage",
        translation_key="water_shortage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.water_shortage_status,
        support_fn=lambda api: api.device_features.is_support_water_mode,
    ),
    RoborockBinarySensorDescription(
        key="dirty_box_full",
        translation_key="dirty_box_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.dirty_water_box_status,
        is_dock_entity=True,
        support_fn=lambda api: api.device_features.is_field_supported(
            StatusV2, StatusField.DIRTY_WATER_BOX_STATUS
        ),
    ),
    RoborockBinarySensorDescription(
        key="clean_box_empty",
        translation_key="clean_box_empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.clear_water_box_status,
        is_dock_entity=True,
        support_fn=lambda api: api.device_features.is_field_supported(
            StatusV2, StatusField.CLEAR_WATER_BOX_STATUS
        ),
    ),
    RoborockBinarySensorDescription(
        key="clean_fluid_empty",
        translation_key="clean_fluid_empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.status.clean_fluid_status == CleanFluidStatus.empty_not_installed
            if data.status.clean_fluid_status is not None
            else None
        ),
        is_dock_entity=True,
        support_fn=lambda api: api.device_features.is_field_supported(
            StatusV2, StatusField.CLEAN_FLUID_STATUS
        ),
    ),
    RoborockBinarySensorDescription(
        key="in_cleaning",
        translation_key="in_cleaning",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.in_cleaning,
    ),
    RoborockBinarySensorDescription(
        key=ATTR_BATTERY_CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            data.status.state
            in (RoborockStateCode.charging, RoborockStateCode.charging_complete)
        ),
    ),
]


ZEO_BINARY_SENSOR_DESCRIPTIONS: list[RoborockBinarySensorDescriptionA01] = [
    RoborockBinarySensorDescriptionA01(
        key="detergent_empty",
        data_protocol=RoborockZeoProtocol.DETERGENT_EMPTY,
        device_class=BinarySensorDeviceClass.PROBLEM,
        translation_key="detergent_empty",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=bool,
    ),
    RoborockBinarySensorDescriptionA01(
        key="softener_empty",
        data_protocol=RoborockZeoProtocol.SOFTENER_EMPTY,
        device_class=BinarySensorDeviceClass.PROBLEM,
        translation_key="softener_empty",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=bool,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum binary sensors."""
    coordinators = config_entry.runtime_data

    @callback
    def async_add_coordinator_entities(
        coordinator: RoborockCoordinatorType,
    ) -> None:
        """Add entities for a specific coordinator."""
        entities: list[BinarySensorEntity] = []
        if isinstance(coordinator, RoborockDataUpdateCoordinator):
            entities.extend(
                RoborockBinarySensorEntity(coordinator, description)
                for description in BINARY_SENSOR_DESCRIPTIONS
                if description.support_fn(coordinator.properties_api)
            )
        elif isinstance(coordinator, RoborockWashingMachineUpdateCoordinator):
            entities.extend(
                RoborockBinarySensorEntityA01(coordinator, description)
                for description in ZEO_BINARY_SENSOR_DESCRIPTIONS
                if description.data_protocol in coordinator.request_protocols
            )
        async_add_entities(entities)

    for coordinator in coordinators.values():
        async_add_coordinator_entities(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"roborock_coordinator_added_{config_entry.entry_id}",
            async_add_coordinator_entities,
        )
    )


class RoborockBinarySensorEntity(RoborockCoordinatedEntityV1, BinarySensorEntity):
    """Representation of a Roborock binary sensor."""

    entity_description: RoborockBinarySensorDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockBinarySensorDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(
            f"{description.key}_{coordinator.duid_slug}",
            coordinator,
            is_dock_entity=description.is_dock_entity,
        )
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the value reported by the sensor."""
        if (data := self.coordinator.data) is not None:
            return bool(self.entity_description.value_fn(data))
        return None


class RoborockBinarySensorEntityA01(RoborockCoordinatedEntityA01, BinarySensorEntity):
    """Representation of a A01 Roborock binary sensor."""

    entity_description: RoborockBinarySensorDescriptionA01

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinatorA01,
        description: RoborockBinarySensorDescriptionA01,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(f"{description.key}_{coordinator.duid_slug}", coordinator)

    @property
    @override
    def is_on(self) -> bool:
        """Return the value reported by the sensor."""
        value = self.coordinator.data[self.entity_description.data_protocol]
        return self.entity_description.value_fn(value)
