"""Support for HERE travel time sensors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HereTravelTimeDataUpdateCoordinator
from .const import (
    ATTR_DESTINATION,
    ATTR_DESTINATION_NAME,
    ATTR_DISTANCE,
    ATTR_DURATION,
    ATTR_DURATION_IN_TRAFFIC,
    ATTR_ORIGIN,
    ATTR_ORIGIN_NAME,
    DOMAIN,
    ICON_CAR,
    ICONS,
    IMPERIAL_UNITS,
)

SCAN_INTERVAL = timedelta(minutes=5)


def sensor_descriptions(travel_mode: str) -> tuple[SensorEntityDescription, ...]:
    """Construct SensorEntityDescriptions."""
    return (
        SensorEntityDescription(
            name="Duration",
            icon=ICONS.get(travel_mode, ICON_CAR),
            key=ATTR_DURATION,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=TIME_MINUTES,
        ),
        SensorEntityDescription(
            name="Duration in traffic",
            icon=ICONS.get(travel_mode, ICON_CAR),
            key=ATTR_DURATION_IN_TRAFFIC,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=TIME_MINUTES,
        ),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add HERE travel time entities from a config_entry."""

    entry_id = config_entry.entry_id
    name = config_entry.data[CONF_NAME]
    coordinator = hass.data[DOMAIN][entry_id]

    sensors: list[HERETravelTimeSensor] = []
    for sensor_description in sensor_descriptions(config_entry.data[CONF_MODE]):
        sensors.append(
            HERETravelTimeSensor(
                entry_id,
                name,
                sensor_description,
                coordinator,
            )
        )
    sensors.append(OriginSensor(entry_id, name, coordinator))
    sensors.append(DestinationSensor(entry_id, name, coordinator))
    sensors.append(DistanceSensor(entry_id, name, coordinator))
    async_add_entities(sensors)


class HERETravelTimeSensor(SensorEntity, CoordinatorEntity):
    """Representation of a HERE travel time sensor."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        sensor_description: SensorEntityDescription,
        coordinator: HereTravelTimeDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = sensor_description
        self._attr_unique_id = f"{unique_id_prefix}_{sensor_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id_prefix)},
            entry_type=DeviceEntryType.SERVICE,
            name=name,
            manufacturer="HERE Technologies",
        )
        self._attr_has_entity_name = True

    async def async_added_to_hass(self) -> None:
        """Wait for start so origin and destination entities can be resolved."""
        await super().async_added_to_hass()

        async def _update_at_start(_):
            await self.async_update()

        self.async_on_remove(async_at_start(self.hass, _update_at_start))

    @property
    def native_value(self) -> str | float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get(self.entity_description.key)
        return None

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get(ATTR_ATTRIBUTION)
        return None


class OriginSensor(HERETravelTimeSensor):
    """Sensor holding information about the route origin."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        coordinator: HereTravelTimeDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        sensor_description = SensorEntityDescription(
            name="Origin",
            icon="mdi:store-marker",
            key=ATTR_ORIGIN_NAME,
        )
        super().__init__(unique_id_prefix, name, sensor_description, coordinator)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """GPS coordinates."""
        if self.coordinator.data is not None:
            return {
                ATTR_LATITUDE: self.coordinator.data[ATTR_ORIGIN].split(",")[0],
                ATTR_LONGITUDE: self.coordinator.data[ATTR_ORIGIN].split(",")[1],
            }
        return None


class DestinationSensor(HERETravelTimeSensor):
    """Sensor holding information about the route destination."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        coordinator: HereTravelTimeDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        sensor_description = SensorEntityDescription(
            name="Destination",
            icon="mdi:store-marker",
            key=ATTR_DESTINATION_NAME,
        )
        super().__init__(unique_id_prefix, name, sensor_description, coordinator)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """GPS coordinates."""
        if self.coordinator.data is not None:
            return {
                ATTR_LATITUDE: self.coordinator.data[ATTR_DESTINATION].split(",")[0],
                ATTR_LONGITUDE: self.coordinator.data[ATTR_DESTINATION].split(",")[1],
            }
        return None


class DistanceSensor(HERETravelTimeSensor):
    """Sensor holding information about the distance."""

    def __init__(
        self,
        unique_id_prefix: str,
        name: str,
        coordinator: HereTravelTimeDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        sensor_description = SensorEntityDescription(
            name="Distance",
            icon=ICONS.get(coordinator.config.travel_mode, ICON_CAR),
            key=ATTR_DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
        )
        super().__init__(unique_id_prefix, name, sensor_description, coordinator)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor."""
        if self.coordinator.config.units == IMPERIAL_UNITS:
            return LENGTH_MILES
        return LENGTH_KILOMETERS
