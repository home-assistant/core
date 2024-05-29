"""Support for Launch Library sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

from pylaunches.types import Event, Launch, StarshipResponse

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util.dt import parse_datetime

from . import LaunchLibraryData
from .const import DOMAIN

DEFAULT_NEXT_LAUNCH_NAME = "Next launch"


@dataclass(frozen=True, kw_only=True)
class LaunchLibrarySensorEntityDescription(SensorEntityDescription):
    """Describes a Next Launch sensor entity."""

    value_fn: Callable[[Launch | Event], datetime | int | str | None]
    attributes_fn: Callable[[Launch | Event], dict[str, Any] | None]
    coordinator: Literal["upcoming_launches", "starship_events"]


SENSOR_DESCRIPTIONS: tuple[LaunchLibrarySensorEntityDescription, ...] = (
    LaunchLibrarySensorEntityDescription(
        key="next_launch",
        icon="mdi:rocket-launch",
        translation_key="next_launch",
        coordinator="upcoming_launches",
        value_fn=lambda nl: nl["name"],
        attributes_fn=lambda nl: {
            "provider": nl["launch_service_provider"]["name"],
            "pad": nl["pad"]["name"],
            "facility": nl["pad"]["location"]["name"],
            "provider_country_code": nl["pad"]["location"]["country_code"],
        },
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_time",
        icon="mdi:clock-outline",
        translation_key="launch_time",
        coordinator="upcoming_launches",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda nl: parse_datetime(nl["net"]),
        attributes_fn=lambda nl: {
            "window_start": nl["window_start"],
            "window_end": nl["window_end"],
            "stream_live": nl["window_start"],
        },
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_probability",
        icon="mdi:dice-multiple",
        translation_key="launch_probability",
        coordinator="upcoming_launches",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda nl: None if nl["probability"] == -1 else nl["probability"],
        attributes_fn=lambda nl: None,
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_status",
        icon="mdi:rocket-launch",
        translation_key="launch_status",
        coordinator="upcoming_launches",
        value_fn=lambda nl: nl["status"]["name"],
        attributes_fn=lambda nl: {"reason": nl.get("holdreason")},
    ),
    LaunchLibrarySensorEntityDescription(
        key="launch_mission",
        icon="mdi:orbit",
        translation_key="launch_mission",
        coordinator="upcoming_launches",
        value_fn=lambda nl: nl["mission"]["name"],
        attributes_fn=lambda nl: {
            "mission_type": nl["mission"]["type"],
            "target_orbit": nl["mission"]["orbit"]["name"],
            "description": nl["mission"]["description"],
        },
    ),
    LaunchLibrarySensorEntityDescription(
        key="starship_launch",
        icon="mdi:rocket",
        translation_key="starship_launch",
        coordinator="starship_events",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda sl: parse_datetime(sl["net"]),
        attributes_fn=lambda sl: {
            "title": sl["mission"]["name"],
            "status": sl["status"]["name"],
            "target_orbit": sl["mission"]["orbit"]["name"],
            "description": sl["mission"]["description"],
        },
    ),
    LaunchLibrarySensorEntityDescription(
        key="starship_event",
        icon="mdi:calendar",
        translation_key="starship_event",
        coordinator="starship_events",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda se: parse_datetime(se["date"]),
        attributes_fn=lambda se: {
            "title": se["name"],
            "location": se["location"],
            "stream": se["video_url"],
            "description": se["description"],
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[LaunchLibraryData],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    name = entry.data.get(CONF_NAME, DEFAULT_NEXT_LAUNCH_NAME)

    async_add_entities(
        (
            LaunchLibrarySensor(
                coordinator=entry.runtime_data[description.coordinator],
                entry_id=entry.entry_id,
                description=description,
                name=name,
            )
            for description in SENSOR_DESCRIPTIONS
        ),
        True,
    )


class LaunchLibrarySensor(
    CoordinatorEntity[DataUpdateCoordinator[list[Launch] | StarshipResponse]],
    SensorEntity,
):
    """Representation of the next launch sensors."""

    _attr_attribution = "Data provided by Launch Library."
    _attr_has_entity_name = True
    _next_event: Launch | Event | None = None
    entity_description: LaunchLibrarySensorEntityDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[Launch] | StarshipResponse],
        entry_id: str,
        description: LaunchLibrarySensorEntityDescription,
        name: str,
    ) -> None:
        """Initialize a Launch Library sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            entry_type=DeviceEntryType.SERVICE,
            name=name,
        )

    @property
    def native_value(self) -> datetime | str | int | None:
        """Return the state of the sensor."""
        if self._next_event is None:
            return None
        return self.entity_description.value_fn(self._next_event)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the sensor."""
        if self._next_event is None:
            return None
        return self.entity_description.attributes_fn(self._next_event)

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return super().available and self._next_event is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if (data := self.coordinator.data) is None:
            return
        if (description_key := self.entity_description.key) == "starship_launch":
            events = cast(StarshipResponse, data)["upcoming"]["launches"]
        elif description_key == "starship_event":
            events = cast(StarshipResponse, data)["upcoming"]["events"]
        else:
            events = data

        self._next_event = next((event for event in events or []), None)
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
