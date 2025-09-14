"""Support for Waze travel time sensor."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_NAME,
    UnitOfLength,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DESTINATION,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_ORIGIN,
    ATTR_ROUTE,
    CONF_VEHICLE_TYPE,
    DEFAULT_NAME,
    DOMAIN,
    ICON_CAR,
    VEHICLE_ICONS,
)
from .coordinator import WazeTravelTimeCoordinator, WazeTravelTimeData


@dataclass(frozen=True, kw_only=True)
class WazeSensorDescription(SensorEntityDescription):
    """Class describing Waze Travel Time sensor entities."""

    value_fn: Callable[[WazeTravelTimeData], float | str | None]


def sensor_descriptions(vehicle_type: str) -> tuple[WazeSensorDescription, ...]:
    """Construct WazeSensorDescriptions."""

    return (
        WazeSensorDescription(
            key=ATTR_DISTANCE,
            translation_key="distance",
            icon=VEHICLE_ICONS.get(vehicle_type, ICON_CAR),
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.DISTANCE,
            native_unit_of_measurement=UnitOfLength.KILOMETERS,
            value_fn=lambda data: data.distance,
        ),
        WazeSensorDescription(
            key=ATTR_ROUTE,
            translation_key="route",
            icon="mdi:routes",
            value_fn=lambda data: data.route,
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Waze travel time sensor entry."""
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    coordinator = config_entry.runtime_data
    entry_id = config_entry.entry_id
    options = config_entry.options

    sensors: list[WazeTravelTimeSensor] = [
        WazeTravelTimeSensor(
            entry_id,
            name,
            sensor_description,
            coordinator,
        )
        for sensor_description in sensor_descriptions(options[CONF_VEHICLE_TYPE])
    ]
    sensors.append(
        DurationSensor(entry_id, name, coordinator, options[CONF_VEHICLE_TYPE])
    )
    sensors.append(OriginSensor(entry_id, name, coordinator))
    sensors.append(DestinationSensor(entry_id, name, coordinator))
    async_add_entities(sensors, False)


class WazeTravelTimeSensor(CoordinatorEntity[WazeTravelTimeCoordinator], SensorEntity):
    """Representation of a Waze travel time sensor."""

    _attr_attribution = "Powered by Waze"
    _attr_has_entity_name = True
    entity_description: WazeSensorDescription

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        description: WazeSensorDescription,
        coordinator: WazeTravelTimeCoordinator,
    ) -> None:
        """Initialize the Waze travel time sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{unique_id_prefix}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=name,
            identifiers={(DOMAIN, DOMAIN)},
            configuration_url="https://www.waze.com",
        )

    @property
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


class DurationSensor(WazeTravelTimeSensor):
    """Sensor holding information about the route origin."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        coordinator: WazeTravelTimeCoordinator,
        vehicle_type: str,
    ) -> None:
        """Initialize the sensor."""
        description = WazeSensorDescription(
            key=ATTR_DURATION,
            translation_key="duration",
            icon=VEHICLE_ICONS.get(vehicle_type, ICON_CAR),
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
            suggested_display_precision=0,
            value_fn=lambda data: data.duration,
        )
        super().__init__(unique_id_prefix, name, description, coordinator)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Legacy attributes."""
        return {
            "duration": self.coordinator.data.duration,
            "distance": self.coordinator.data.distance,
            "route": self.coordinator.data.route,
            "origin": self.coordinator.data.origin,
            "destination": self.coordinator.data.destination,
        }


class OriginSensor(WazeTravelTimeSensor):
    """Sensor holding information about the route origin."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        coordinator: WazeTravelTimeCoordinator,
    ) -> None:
        """Initialize the sensor."""
        description = WazeSensorDescription(
            key=ATTR_ORIGIN,
            translation_key="origin",
            icon="mdi:store-marker",
            value_fn=lambda data: data.origin,
        )
        super().__init__(unique_id_prefix, name, description, coordinator)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """GPS coordinates."""
        if (
            self.coordinator.data.origin_coordinates is None
            or "," not in self.coordinator.data.origin_coordinates
        ):
            return None

        return {
            ATTR_LATITUDE: self.coordinator.data.origin_coordinates.split(",")[0],
            ATTR_LONGITUDE: self.coordinator.data.origin_coordinates.split(",")[1],
        }


class DestinationSensor(WazeTravelTimeSensor):
    """Sensor holding information about the route destination."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        coordinator: WazeTravelTimeCoordinator,
    ) -> None:
        """Initialize the sensor."""
        description = WazeSensorDescription(
            key=ATTR_DESTINATION,
            translation_key="destination",
            icon="mdi:store-marker",
            value_fn=lambda data: data.destination,
        )
        super().__init__(unique_id_prefix, name, description, coordinator)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """GPS coordinates."""
        if (
            self.coordinator.data.destination_coordinates is None
            or "," not in self.coordinator.data.destination_coordinates
        ):
            return None

        return {
            ATTR_LATITUDE: self.coordinator.data.destination_coordinates.split(",")[0],
            ATTR_LONGITUDE: self.coordinator.data.destination_coordinates.split(",")[1],
        }
