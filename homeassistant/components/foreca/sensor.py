"""Sensor platform for the Foreca integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pyforeca import Observation

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import OptionalRequest, symbol_to_condition
from .coordinator import ForecaConfigEntry, ForecaUpdateCoordinator, ForecaWeatherData
from .entity import ForecaEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ForecaSensorEntityDescription(SensorEntityDescription):
    """Describes a Foreca sensor entity."""

    value_fn: Callable[[ForecaWeatherData], StateType | datetime]
    request: OptionalRequest | None = None


CONDITIONS = [
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
]


def _observed(
    value_fn: Callable[[Observation], StateType | datetime],
) -> Callable[[ForecaWeatherData], StateType | datetime]:
    """Read a value from the nearest station's latest observation."""

    def read(data: ForecaWeatherData) -> StateType | datetime:
        if data.observation is None:
            return None
        return value_fn(data.observation)

    return read


SENSOR_TYPES: tuple[ForecaSensorEntityDescription, ...] = (
    ForecaSensorEntityDescription(
        key="precipitation_intensity",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.current.precip_rate,
    ),
    ForecaSensorEntityDescription(
        key="thunderstorm_probability",
        translation_key="thunderstorm_probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.current.thunder_prob,
    ),
    ForecaSensorEntityDescription(
        key="precipitation_probability",
        translation_key="precipitation_probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.current.precip_prob,
    ),
    ForecaSensorEntityDescription(
        key="observation_station",
        translation_key="observation_station",
        entity_category=EntityCategory.DIAGNOSTIC,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.station),
    ),
    ForecaSensorEntityDescription(
        key="observation_time",
        translation_key="observation_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(
            lambda obs: dt_util.parse_datetime(obs.time) if obs.time else None
        ),
    ),
    ForecaSensorEntityDescription(
        key="observed_condition",
        translation_key="observed_condition",
        device_class=SensorDeviceClass.ENUM,
        options=CONDITIONS,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: symbol_to_condition(obs.symbol)),
    ),
    ForecaSensorEntityDescription(
        key="observed_temperature",
        translation_key="observed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.temperature),
    ),
    ForecaSensorEntityDescription(
        key="observed_apparent_temperature",
        translation_key="observed_apparent_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.feels_like_temp),
    ),
    ForecaSensorEntityDescription(
        key="observed_humidity",
        translation_key="observed_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.rel_humidity),
    ),
    ForecaSensorEntityDescription(
        key="observed_pressure",
        translation_key="observed_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.pressure),
    ),
    ForecaSensorEntityDescription(
        key="observed_wind_speed",
        translation_key="observed_wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.wind_speed),
    ),
    ForecaSensorEntityDescription(
        key="observed_wind_gust_speed",
        translation_key="observed_wind_gust_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.wind_gust),
    ),
    ForecaSensorEntityDescription(
        key="observed_wind_direction",
        translation_key="observed_wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.wind_dir),
    ),
    ForecaSensorEntityDescription(
        key="observed_visibility",
        translation_key="observed_visibility",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(
            lambda obs: obs.visibility / 1000 if obs.visibility is not None else None
        ),
    ),
    ForecaSensorEntityDescription(
        key="observed_snow_depth",
        translation_key="observed_snow_depth",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        request=OptionalRequest.OBSERVATION,
        value_fn=_observed(lambda obs: obs.snow_depth),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForecaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Foreca sensors for every configured location."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            (
                ForecaSensor(coordinator, subentry_id, description)
                for description in SENSOR_TYPES
            ),
            config_subentry_id=subentry_id,
        )


class ForecaSensor(ForecaEntity, SensorEntity):
    """Define a Foreca sensor."""

    entity_description: ForecaSensorEntityDescription

    def __init__(
        self,
        coordinator: ForecaUpdateCoordinator,
        subentry_id: str,
        description: ForecaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{subentry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        """Return if the request this sensor reads from succeeded."""
        return super().available and (
            self.entity_description.request not in self.coordinator.data.failed_requests
        )

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
