"""Binary sensors for the Moon integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MoonConfigEntry
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import MoonData, MoonUpdateCoordinator

ENTITY_ID_BINARY_SENSOR_FORMAT = BINARY_SENSOR_DOMAIN + ".moon_{}"


@dataclass(kw_only=True, frozen=True)
class MoonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a moon binary sensor."""

    value_fn: Callable[[MoonData], bool | None]


BINARY_SENSOR_TYPES: tuple[MoonBinarySensorEntityDescription, ...] = (
    MoonBinarySensorEntityDescription(
        key="above_horizon",
        translation_key="above_horizon",
        value_fn=lambda data: data.above_horizon,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MoonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities(
        MoonBinarySensorEntity(entry, entry.runtime_data, description)
        for description in BINARY_SENSOR_TYPES
    )


class MoonBinarySensorEntity(
    CoordinatorEntity[MoonUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Moon binary sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: MoonBinarySensorEntityDescription

    def __init__(
        self,
        entry: MoonConfigEntry,
        coordinator: MoonUpdateCoordinator,
        description: MoonBinarySensorEntityDescription,
    ) -> None:
        """Initialize the moon binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.entity_id = ENTITY_ID_BINARY_SENSOR_FORMAT.format(description.key)
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"
        self._attr_device_info = DeviceInfo(
            name=DEFAULT_NAME,
            identifiers={(DOMAIN, entry.entry_id)},
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
