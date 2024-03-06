"""Implementation of the Radarr sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from overseerr_api.models import RequestCountGet200Response

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OverseerrUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class OverseerrSensorEntityDescription(SensorEntityDescription):
    """Entity description class for Overseerr sensors."""

    value_fn: Callable[[RequestCountGet200Response], StateType]


SENSOR_TYPES: tuple[OverseerrSensorEntityDescription, ...] = (
    OverseerrSensorEntityDescription(
        key="requested_movies",
        translation_key="requested_movies",
        value_fn=lambda data: data.movie,
    ),
    OverseerrSensorEntityDescription(
        key="requested_tv",
        translation_key="requested_tv",
        value_fn=lambda data: data.tv,
    ),
    OverseerrSensorEntityDescription(
        key="requested_pending",
        translation_key="requested_pending",
        value_fn=lambda data: data.pending,
    ),
    OverseerrSensorEntityDescription(
        key="requested_approved",
        translation_key="requested_approved",
        value_fn=lambda data: data.approved,
    ),
    OverseerrSensorEntityDescription(
        key="requested_available",
        translation_key="requested_available",
        value_fn=lambda data: data.available,
    ),
    OverseerrSensorEntityDescription(
        key="requested_total",
        translation_key="requested_total",
        value_fn=lambda data: data.total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    coordinator: OverseerrUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        OverseeerrRequestsSensor(coordinator, config_entry, description)
        for description in SENSOR_TYPES
    )


class OverseeerrRequestsSensor(
    CoordinatorEntity[OverseerrUpdateCoordinator], SensorEntity
):
    """Representation of Overseerr total requests."""

    _attr_has_entity_name = True
    entity_description: OverseerrSensorEntityDescription

    def __init__(
        self,
        coordinator: OverseerrUpdateCoordinator,
        config_entry,
        entity_description: OverseerrSensorEntityDescription,
    ) -> None:
        """Initialize the Overseerr sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{config_entry.entry_id}-{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Overseerr",
        )

    @property
    def native_value(self) -> StateType:
        """Return the value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
