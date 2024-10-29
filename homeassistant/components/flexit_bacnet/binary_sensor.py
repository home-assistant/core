"""The Flexit Nordic (BACnet) integration."""

from collections.abc import Callable
from dataclasses import dataclass

from flexit_bacnet import FlexitBACnet

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FlexitCoordinator
from .const import DOMAIN
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
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Flexit (bacnet) binary sensor from a config entry."""
    coordinator: FlexitCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        FlexitBinarySensor(coordinator, description) for description in SENSOR_TYPES
    )


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
