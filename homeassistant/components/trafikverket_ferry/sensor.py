"""Ferry information for departures, provided by Trafikverket."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_utc

from . import TVFerryConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import TVDataUpdateCoordinator

ATTR_FROM = "from_harbour"
ATTR_TO = "to_harbour"
ATTR_MODIFIED_TIME = "modified_time"
ATTR_OTHER_INFO = "other_info"

SCAN_INTERVAL = timedelta(minutes=5)


@dataclass(frozen=True, kw_only=True)
class TrafikverketSensorEntityDescription(SensorEntityDescription):
    """Describes Trafikverket sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType | datetime]
    info_fn: Callable[[dict[str, Any]], StateType | list] | None


SENSOR_TYPES: tuple[TrafikverketSensorEntityDescription, ...] = (
    TrafikverketSensorEntityDescription(
        key="departure_time",
        translation_key="departure_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: as_utc(data["departure_time"]),
        info_fn=lambda data: cast(list[str], data["departure_information"]),
    ),
    TrafikverketSensorEntityDescription(
        key="departure_from",
        translation_key="departure_from",
        value_fn=lambda data: cast(str, data["departure_from"]),
        info_fn=lambda data: cast(list[str], data["departure_information"]),
    ),
    TrafikverketSensorEntityDescription(
        key="departure_to",
        translation_key="departure_to",
        value_fn=lambda data: cast(str, data["departure_to"]),
        info_fn=lambda data: cast(list[str], data["departure_information"]),
    ),
    TrafikverketSensorEntityDescription(
        key="departure_modified",
        translation_key="departure_modified",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: as_utc(data["departure_modified"]),
        info_fn=lambda data: cast(list[str], data["departure_information"]),
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="departure_time_next",
        translation_key="departure_time_next",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: as_utc(data["departure_time_next"]),
        info_fn=None,
        entity_registry_enabled_default=False,
    ),
    TrafikverketSensorEntityDescription(
        key="departure_time_next_next",
        translation_key="departure_time_next_next",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: as_utc(data["departure_time_next_next"]),
        info_fn=None,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TVFerryConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Trafikverket sensor entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        [
            FerrySensor(coordinator, entry.data[CONF_NAME], entry.entry_id, description)
            for description in SENSOR_TYPES
        ]
    )


class FerrySensor(CoordinatorEntity[TVDataUpdateCoordinator], SensorEntity):
    """Contains data about a ferry departure."""

    entity_description: TrafikverketSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TVDataUpdateCoordinator,
        name: str,
        entry_id: str,
        entity_description: TrafikverketSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}-{entity_description.key}"
        self.entity_description = entity_description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Trafikverket",
            model="v2.0",
            name=name,
            configuration_url="https://api.trafikinfo.trafikverket.se/",
        )
        self._update_attr()

    def _update_attr(self) -> None:
        """Update _attr."""
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )

        if self.entity_description.info_fn:
            self._attr_extra_state_attributes = {
                "other_information": self.entity_description.info_fn(
                    self.coordinator.data
                ),
            }

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_attr()
        return super()._handle_coordinator_update()
