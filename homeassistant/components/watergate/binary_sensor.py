"""Support for Watergate binary sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    WatergateAgregatedRequests,
    WatergateConfigEntry,
    WatergateDataCoordinator,
)
from .entity import WatergateEntity

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class WatergateBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for Watergate binary sensor entities."""

    value_fn: Callable[[WatergateAgregatedRequests], bool | None]


DESCRIPTIONS: list[WatergateBinarySensorEntityDescription] = [
    WatergateBinarySensorEntityDescription(
        value_fn=lambda data: data.state.water_flow_indicator if data.state else None,
        translation_key="water_flowing",
        key="water_flowing",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    WatergateBinarySensorEntityDescription(
        value_fn=lambda data: (
            data.networking.mqtt_connected if data.networking else None
        ),
        translation_key="mqtt_connected",
        key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    WatergateBinarySensorEntityDescription(
        value_fn=lambda data: (
            data.networking.wifi_connected if data.networking else None
        ),
        translation_key="wifi_connected",
        key="wifi_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up all binary sensors for the Watergate platform."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        SonicBinarySensor(coordinator, description) for description in DESCRIPTIONS
    )


class SonicBinarySensor(WatergateEntity, BinarySensorEntity):
    """Define a Sonic binary sensor entity."""

    entity_description: WatergateBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
        entity_description: WatergateBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.entity_description.value_fn(self.coordinator.data) is not None
        )
