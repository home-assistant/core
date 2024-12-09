"""Sensors for cloud based weatherflow."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from weatherflow4py.models.rest.observation import Observation
from weatherflow4py.models.ws.websocket_request import (
    ListenStartMessage,
    RapidWindListenStartMessage,
)
from weatherflow4py.models.ws.websocket_response import (
    EventDataRapidWind,
    WebsocketObservation,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import UTC

from . import (
    WeatherFlowCloudDataCallbackCoordinator,
    WeatherFlowCloudUpdateCoordinatorREST,
    WeatherFlowCoordinators,
)
from .const import DOMAIN, REST_API, WEBSOCKET_API
from .entity import WeatherFlowCloudEntity


def _get_wind_direction_icon(degree: int) -> str:
    """Get the wind direction icon based on the degree."""

    # degree = event.wind_direction_degrees

    if not 0 <= degree <= 360:
        raise ValueError("Degree must be between 0 and 360")

    # Normalize the degree to be within 0-360 range
    degree = degree % 360

    # Define direction ranges
    directions = [
        (0, "mdi:arrow-up"),
        (45, "mdi:arrow-top-right"),
        (90, "mdi:arrow-right"),
        (135, "mdi:arrow-bottom-right"),
        (180, "mdi:arrow-down"),
        (225, "mdi:arrow-bottom-left"),
        (270, "mdi:arrow-left"),
        (315, "mdi:arrow-top-left"),
        (360, "mdi:arrow-up"),
    ]

    # Find the appropriate direction
    for angle, icon in directions:
        if degree < angle + 22.5:
            return icon

    # This line should never be reached, but it's here for completeness
    return "mdi:arrow-up"


@dataclass(frozen=True, kw_only=True)
class WeatherFlowCloudSensorEntityDescription(
    SensorEntityDescription,
):
    """Describes a weatherflow sensor."""

    value_fn: Callable[[Observation], StateType | datetime]


@dataclass(frozen=True, kw_only=True)
class WeatherFlowCloudSensorEntityDescriptionWebsocketWind(
    SensorEntityDescription,
):
    """Describes a weatherflow sensor."""

    value_fn: Callable[[EventDataRapidWind], StateType | datetime]
    icon_fn: Callable[[int], str] | None = None


@dataclass(frozen=True, kw_only=True)
class WeatherFlowCloudSensorEntityDescriptionWebsocketObservation(
    SensorEntityDescription,
):
    """Describes a weatherflow sensor."""

    value_fn: Callable[[WebsocketObservation], StateType | datetime]


WEBSOCKET_WIND_SENSORS: tuple[
    WeatherFlowCloudSensorEntityDescriptionWebsocketWind, ...
] = (
    WeatherFlowCloudSensorEntityDescriptionWebsocketWind(
        key="wind_speed",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.WIND_SPEED,
        suggested_display_precision=1,
        value_fn=lambda data: data.wind_speed_meters_per_second,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    ),
    WeatherFlowCloudSensorEntityDescriptionWebsocketWind(
        key="wind_direction",
        translation_key="wind_direction",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.wind_direction_degrees,
        icon_fn=_get_wind_direction_icon,
        native_unit_of_measurement="°",
    ),
)

WEBSOCKET_OBSERVATION_SENSORS: tuple[
    WeatherFlowCloudSensorEntityDescriptionWebsocketObservation, ...
] = (
    WeatherFlowCloudSensorEntityDescriptionWebsocketObservation(
        key="wind_lull",
        translation_key="wind_lull",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.WIND_SPEED,
        suggested_display_precision=1,
        value_fn=lambda data: data.wind_lull,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        icon="mdi:weather-windy-variant",
    ),
    WeatherFlowCloudSensorEntityDescriptionWebsocketObservation(
        key="wind_gust",
        translation_key="wind_gust",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.WIND_SPEED,
        suggested_display_precision=1,
        value_fn=lambda data: data.wind_gust,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        icon="mdi:weather-dust",
    ),
    WeatherFlowCloudSensorEntityDescriptionWebsocketObservation(
        key="wind_avg",
        translation_key="wind_avg",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.WIND_SPEED,
        suggested_display_precision=1,
        value_fn=lambda data: data.wind_avg,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
    ),
    WeatherFlowCloudSensorEntityDescriptionWebsocketObservation(
        key="wind_sample_interval",
        translation_key="wind_sample_interval",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.wind_sample_interval,
    ),
)


WF_SENSORS: tuple[WeatherFlowCloudSensorEntityDescription, ...] = (
    # Air Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="air_density",
        translation_key="air_density",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        value_fn=lambda data: data.air_density,
        native_unit_of_measurement="kg/m³",
    ),
    # Temp Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.air_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        value_fn=lambda data: data.dew_point,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="feels_like",
        translation_key="feels_like",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.feels_like,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="heat_index",
        translation_key="heat_index",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.heat_index,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wind_chill",
        translation_key="wind_chill",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.wind_chill,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wet_bulb_temperature",
        translation_key="wet_bulb_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.wet_bulb_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="wet_bulb_globe_temperature",
        translation_key="wet_bulb_globe_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.wet_bulb_globe_temperature,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    # Pressure Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="barometric_pressure",
        translation_key="barometric_pressure",
        value_fn=lambda data: data.barometric_pressure,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="sea_level_pressure",
        translation_key="sea_level_pressure",
        value_fn=lambda data: data.sea_level_pressure,
        native_unit_of_measurement=UnitOfPressure.MBAR,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
    ),
    # Lightning Sensors
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count",
        translation_key="lightning_strike_count",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.lightning_strike_count,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count_last_1hr",
        translation_key="lightning_strike_count_last_1hr",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.lightning_strike_count_last_1hr,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_count_last_3hr",
        translation_key="lightning_strike_count_last_3hr",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.lightning_strike_count_last_3hr,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_last_distance",
        translation_key="lightning_strike_last_distance",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda data: data.lightning_strike_last_distance,
    ),
    WeatherFlowCloudSensorEntityDescription(
        key="lightning_strike_last_epoch",
        translation_key="lightning_strike_last_epoch",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=(
            lambda data: datetime.fromtimestamp(
                data.lightning_strike_last_epoch, tz=UTC
            )
            if data.lightning_strike_last_epoch is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WeatherFlow sensors based on a config entry."""

    coordinators: WeatherFlowCoordinators = hass.data[DOMAIN][entry.entry_id]
    rest_coordinator = coordinators.rest
    wind_coordinator: WeatherFlowCloudDataCallbackCoordinator[
        EventDataRapidWind, EventDataRapidWind, RapidWindListenStartMessage
    ] = coordinators.wind
    observation_coordinator: WeatherFlowCloudDataCallbackCoordinator[
        WebsocketObservation, WebsocketObservation, ListenStartMessage
    ] = coordinators.observation

    entities: list[SensorEntity] = []
    entities.extend(
        WeatherFlowCloudSensorREST(rest_coordinator, sensor_description, station_id)
        for station_id in rest_coordinator.data
        for sensor_description in WF_SENSORS
    )

    entities.extend(
        WeatherFlowWebsocketSensorWind(
            coordinator=wind_coordinator,
            description=sensor_description,
            station_id=station_id,
            device_id=device_id,
        )
        for station_id in wind_coordinator.stations.station_outdoor_device_map
        for device_id in wind_coordinator.stations.station_outdoor_device_map[
            station_id
        ]
        for sensor_description in WEBSOCKET_WIND_SENSORS
    )

    entities.extend(
        WeatherFlowWebsocketSensorObservation(
            coordinator=observation_coordinator,
            description=sensor_description,
            station_id=station_id,
            device_id=device_id,
        )
        for station_id in observation_coordinator.stations.station_outdoor_device_map
        for device_id in observation_coordinator.stations.station_outdoor_device_map[
            station_id
        ]
        for sensor_description in WEBSOCKET_OBSERVATION_SENSORS
    )
    async_add_entities(entities)


class WeatherFlowSensorBase(WeatherFlowCloudEntity, SensorEntity, ABC):
    """Common base class."""

    _attr_extra_state_attributes: dict[str, str]

    def __init__(
        self,
        coordinator: Any,
        description: WeatherFlowCloudSensorEntityDescription
        | WeatherFlowCloudSensorEntityDescriptionWebsocketWind
        | WeatherFlowCloudSensorEntityDescriptionWebsocketObservation,
        station_id: int,
        device_id: int | None = None,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator, station_id)
        self.station_id = station_id
        self.device_id = device_id
        self.entity_description = description
        self._attr_unique_id = self._generate_unique_id()

    def _generate_unique_id(self) -> str:
        """Generate a unique ID for the sensor."""
        if self.device_id is not None:
            return f"{self.station_id}_{self.device_id}_{self.entity_description.key}"
        return f"{self.station_id}_{self.entity_description.key}"

    @property
    @abstractmethod
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Abstract method for native value."""

    @property
    def available(self) -> bool:
        """Get if available."""
        if self.device_id is not None:
            return bool(
                self.coordinator.data
                and self.coordinator.data[self.station_id][self.device_id] is not None
            )
        return bool(self.coordinator.data)


class WeatherFlowWebsocketSensorObservation(WeatherFlowSensorBase):
    """Class for Websocket Observations."""

    entity_description: WeatherFlowCloudSensorEntityDescriptionWebsocketObservation
    _attr_extra_state_attributes = {"Data source": WEBSOCKET_API}

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        """Return the native value."""
        if self.coordinator.data and self.device_id is not None:
            data = self.coordinator.data[self.station_id][self.device_id]
            return self.entity_description.value_fn(data)
        return None


class WeatherFlowWebsocketSensorWind(WeatherFlowSensorBase):
    """Class for wind over websockets."""

    entity_description: WeatherFlowCloudSensorEntityDescriptionWebsocketWind
    _attr_extra_state_attributes = {"Data source": WEBSOCKET_API}

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native value."""

        if self.coordinator.data and self.device_id is not None:
            data = self.coordinator.data[self.station_id][self.device_id]
            return self.entity_description.value_fn(data)

        return None

    @property
    def icon(self) -> str | None:
        """Get icon."""

        value = (
            int(self.native_value)
            if self.native_value is not None
            and isinstance(self.native_value, (int, float, str))
            else None
        )

        if value and self.entity_description.icon_fn is not None:
            return self.entity_description.icon_fn(value)
        return None


class WeatherFlowCloudSensorREST(WeatherFlowSensorBase):
    """Class for a REST based sensor."""

    entity_description: WeatherFlowCloudSensorEntityDescription
    _attr_extra_state_attributes = {"Data source": REST_API}
    coordinator: WeatherFlowCloudUpdateCoordinatorREST

    @property
    def native_value(self) -> StateType | datetime:
        """Return the native value."""
        if self.coordinator.data:
            return self.entity_description.value_fn(
                self.coordinator.data[self.station_id].observation.obs[0]
            )
        return None
