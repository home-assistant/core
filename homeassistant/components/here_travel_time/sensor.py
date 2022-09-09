"""Support for HERE travel time sensors."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    CONF_MODE,
    CONF_NAME,
    CONF_UNIT_SYSTEM,
    TIME_MINUTES,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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
    ATTR_ROUTE,
    CONF_ARRIVAL,
    CONF_DEPARTURE,
    CONF_DESTINATION_ENTITY_ID,
    CONF_DESTINATION_LATITUDE,
    CONF_DESTINATION_LONGITUDE,
    CONF_ORIGIN_ENTITY_ID,
    CONF_ORIGIN_LATITUDE,
    CONF_ORIGIN_LONGITUDE,
    CONF_ROUTE_MODE,
    CONF_TRAFFIC_MODE,
    DEFAULT_NAME,
    DOMAIN,
    ICON_CAR,
    ICONS,
    ROUTE_MODE_FASTEST,
    ROUTE_MODES,
    TRAVEL_MODE_BICYCLE,
    TRAVEL_MODE_CAR,
    TRAVEL_MODE_PEDESTRIAN,
    TRAVEL_MODE_PUBLIC,
    TRAVEL_MODE_PUBLIC_TIME_TABLE,
    TRAVEL_MODE_TRUCK,
    TRAVEL_MODES,
    UNITS,
)

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Inclusive(
            CONF_DESTINATION_LATITUDE, "destination_coordinates"
        ): cv.latitude,
        vol.Inclusive(
            CONF_DESTINATION_LONGITUDE, "destination_coordinates"
        ): cv.longitude,
        vol.Exclusive(CONF_DESTINATION_LATITUDE, "destination"): cv.latitude,
        vol.Exclusive(CONF_DESTINATION_ENTITY_ID, "destination"): cv.entity_id,
        vol.Inclusive(CONF_ORIGIN_LATITUDE, "origin_coordinates"): cv.latitude,
        vol.Inclusive(CONF_ORIGIN_LONGITUDE, "origin_coordinates"): cv.longitude,
        vol.Exclusive(CONF_ORIGIN_LATITUDE, "origin"): cv.latitude,
        vol.Exclusive(CONF_ORIGIN_ENTITY_ID, "origin"): cv.entity_id,
        vol.Optional(CONF_DEPARTURE): cv.time,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODE, default=TRAVEL_MODE_CAR): vol.In(TRAVEL_MODES),
        vol.Optional(CONF_ROUTE_MODE, default=ROUTE_MODE_FASTEST): vol.In(ROUTE_MODES),
        vol.Optional(CONF_TRAFFIC_MODE, default=False): cv.boolean,
        vol.Optional(CONF_UNIT_SYSTEM): vol.In(UNITS),
    }
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_DESTINATION_LATITUDE, CONF_DESTINATION_ENTITY_ID),
    cv.has_at_least_one_key(CONF_ORIGIN_LATITUDE, CONF_ORIGIN_ENTITY_ID),
    cv.key_value_schemas(
        CONF_MODE,
        {
            None: PLATFORM_SCHEMA,
            TRAVEL_MODE_BICYCLE: PLATFORM_SCHEMA,
            TRAVEL_MODE_CAR: PLATFORM_SCHEMA,
            TRAVEL_MODE_PEDESTRIAN: PLATFORM_SCHEMA,
            TRAVEL_MODE_PUBLIC: PLATFORM_SCHEMA,
            TRAVEL_MODE_TRUCK: PLATFORM_SCHEMA,
            TRAVEL_MODE_PUBLIC_TIME_TABLE: PLATFORM_SCHEMA.extend(
                {
                    vol.Exclusive(CONF_ARRIVAL, "arrival_departure"): cv.time,
                    vol.Exclusive(CONF_DEPARTURE, "arrival_departure"): cv.time,
                }
            ),
        },
    ),
)


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
            name="Duration in Traffic",
            icon=ICONS.get(travel_mode, ICON_CAR),
            key=ATTR_DURATION_IN_TRAFFIC,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=TIME_MINUTES,
        ),
        SensorEntityDescription(
            name="Distance",
            icon=ICONS.get(travel_mode, ICON_CAR),
            key=ATTR_DISTANCE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        SensorEntityDescription(
            name="Route",
            icon="mdi:directions",
            key=ATTR_ROUTE,
        ),
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the HERE travel time platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )

    _LOGGER.warning(
        "Your HERE travel time configuration has been imported into the UI; "
        "please remove it from configuration.yaml as support for it will be "
        "removed in a future release"
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
        self._attr_name = f"{name} {sensor_description.name}"
        self._attr_unique_id = f"{unique_id_prefix}_{sensor_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id_prefix)},
            entry_type=DeviceEntryType.SERVICE,
            name=name,
            manufacturer="HERE Technologies",
        )

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
