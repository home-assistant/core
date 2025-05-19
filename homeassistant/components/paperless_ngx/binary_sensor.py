"""Binary sensor support for Paperless-ngx."""

from __future__ import annotations

from _collections_abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_flow import PaperlessConfigEntry
from .coordinator import PaperlessCoordinator, PaperlessData
from .entity import PaperlessCoordinatorEntity


@dataclass(frozen=True, kw_only=True)
class PaperlessBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Paperless-ngx binary sensor entity."""

    value_fn: Callable[[PaperlessData], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[PaperlessBinarySensorEntityDescription, ...] = (
    PaperlessBinarySensorEntityDescription(
        key="update_available",
        translation_key="update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.remote_version.update_available
        if data.remote_version is not None
        else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx binary sensors."""

    async_add_entities(
        [
            PaperlessBinarySensor(
                entry=entry,
                coordinator=entry.runtime_data,
                description=description,
            )
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class PaperlessBinarySensor(
    PaperlessCoordinatorEntity[PaperlessCoordinator],
    BinarySensorEntity,
):
    """Defines a Paperless-ngx binary sensor."""

    entity_description: PaperlessBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: PaperlessCoordinator,
        entry: PaperlessConfigEntry,
        description: PaperlessBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(
            entry=entry,
            coordinator=coordinator,
            description=description,
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value_fn = self.entity_description.value_fn
        return value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.is_on is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
