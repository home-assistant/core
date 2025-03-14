"""The Flexit Nordic (BACnet) integration."""

from collections.abc import Callable
from dataclasses import dataclass

from flexit_bacnet import FlexitBACnet

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import FlexitConfigEntry, FlexitCoordinator
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Flexit binary sensor entity."""

    value_fn: Callable[[FlexitBACnet], bool]


SENSOR_TYPES: tuple[FlexitBinarySensorEntityDescription, ...] = (
    FlexitBinarySensorEntityDescription(
        key="air_filter_polluted",
        device_class=BinarySensorDeviceClass.PROBLEM,
        translation_key="air_filter_polluted",
        value_fn=lambda data: data.air_filter_polluted,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) binary sensor from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        FlexitBinarySensor(coordinator, description) for description in SENSOR_TYPES
    )


# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class FlexitBinarySensor(FlexitEntity, BinarySensorEntity):
    """Representation of a Flexit binary Sensor."""

    entity_description: FlexitBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: FlexitCoordinator,
        entity_description: FlexitBinarySensorEntityDescription,
    ) -> None:
        """Initialize Flexit (bacnet) sensor."""
        super().__init__(coordinator)

        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.device.serial_number}-{entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return value of binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
