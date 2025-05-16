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

from .const import DOMAIN, ENTITY_SENSOR_UPDATE_AVAILABLE
from .coordinator import (
    PaperlessConfigEntry,
    PaperlessCoordinator,
    PaperlessData,
    PaperlessRuntimeData,
)
from .entity import PaperlessCoordinatorEntity
from .helpers import build_state_fn


@dataclass(frozen=True, kw_only=True)
class PaperlessBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Paperless-ngx binary sensor entity."""

    value_fn: Callable[[PaperlessData], bool | None]
    attributes_fn: Callable[[PaperlessData], dict[str, str | None]] | None = None


BINARY_SENSOR_DESCRIPTIONS: tuple[PaperlessBinarySensorEntityDescription, ...] = (
    PaperlessBinarySensorEntityDescription(
        key=ENTITY_SENSOR_UPDATE_AVAILABLE,
        translation_key=ENTITY_SENSOR_UPDATE_AVAILABLE,
        icon="mdi:update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=build_state_fn(
            lambda data: data.remote_version.update_available
            if data.remote_version is not None
            else None,
        ),
        attributes_fn=lambda data: {
            "latest_version": str(data.remote_version.version)
            if data.remote_version is not None
            else None,
            "last_checked": str(data.remote_version_last_checked),
        },
    ),
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
        data: PaperlessRuntimeData,
        entry: PaperlessConfigEntry,
        description: PaperlessBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(data, entry, description, coordinator)
        self.paperless_data = data
        self._attr_unique_id = (
            f"{DOMAIN}__{entry.entry_id}_binary_sensor_{description.key}"
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value_fn = self.entity_description.value_fn
        return value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        attributes_fn = self.entity_description.attributes_fn
        if attributes_fn:
            return attributes_fn(self.coordinator.data)
        return {}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.is_on is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PaperlessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Paperless-ngx binary sensors."""
    data = entry.runtime_data

    async_add_entities(
        [
            PaperlessBinarySensor(data.coordinator, data, entry, description)
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]
    )
