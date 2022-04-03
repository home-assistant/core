"""Sensor component that handles additional Tomorrowio data for your location."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pytomorrowio.const import (
    HealthConcernType,
    PollenIndex,
    PrecipitationType,
    PrimaryPollutantType,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_NAME,
    IRRADIATION_BTUS_PER_HOUR_SQUARE_FOOT,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from homeassistant.util.distance import convert as distance_convert
from homeassistant.util.pressure import convert as pressure_convert
from homeassistant.util.temperature import convert as temp_convert

from . import TomorrowioDataUpdateCoordinator, TomorrowioEntity
from .const import (
    DOMAIN,
    TMRW_ATTR_CARBON_MONOXIDE,
    TMRW_ATTR_CHINA_AQI,
    TMRW_ATTR_CHINA_HEALTH_CONCERN,
    TMRW_ATTR_CHINA_PRIMARY_POLLUTANT,
    TMRW_ATTR_CLOUD_BASE,
    TMRW_ATTR_CLOUD_CEILING,
    TMRW_ATTR_CLOUD_COVER,
    TMRW_ATTR_DEW_POINT,
    TMRW_ATTR_EPA_AQI,
    TMRW_ATTR_EPA_HEALTH_CONCERN,
    TMRW_ATTR_EPA_PRIMARY_POLLUTANT,
    TMRW_ATTR_FEELS_LIKE,
    TMRW_ATTR_FIRE_INDEX,
    TMRW_ATTR_NITROGEN_DIOXIDE,
    TMRW_ATTR_OZONE,
    TMRW_ATTR_PARTICULATE_MATTER_10,
    TMRW_ATTR_PARTICULATE_MATTER_25,
    TMRW_ATTR_POLLEN_GRASS,
    TMRW_ATTR_POLLEN_TREE,
    TMRW_ATTR_POLLEN_WEED,
    TMRW_ATTR_PRECIPITATION_TYPE,
    TMRW_ATTR_PRESSURE_SURFACE_LEVEL,
    TMRW_ATTR_SOLAR_GHI,
    TMRW_ATTR_SULPHUR_DIOXIDE,
    TMRW_ATTR_WIND_GUST,
)


@dataclass
class TomorrowioSensorEntityDescription(SensorEntityDescription):
    """Describes a Tomorrow.io sensor entity."""

    unit_imperial: str | None = None
    unit_metric: str | None = None
    multiplication_factor: float | None = None
    metric_conversion: Callable[[float], float] | float | None = None
    value_map: Any | None = None

    def __post_init__(self) -> None:
        """Handle post init."""
        if self.unit_imperial != self.unit_metric and (
            self.unit_imperial is None or self.unit_metric is None
        ):
            raise ValueError(
                "Entity descriptions must specify both or neither imperial and metric units"
            )


SENSOR_TYPES = (
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_FEELS_LIKE,
        name="Feels Like",
        unit_imperial=TEMP_FAHRENHEIT,
        unit_metric=TEMP_CELSIUS,
        metric_conversion=lambda val: temp_convert(val, TEMP_FAHRENHEIT, TEMP_CELSIUS),
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_DEW_POINT,
        name="Dew Point",
        unit_imperial=TEMP_FAHRENHEIT,
        unit_metric=TEMP_CELSIUS,
        metric_conversion=lambda val: temp_convert(val, TEMP_FAHRENHEIT, TEMP_CELSIUS),
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PRESSURE_SURFACE_LEVEL,
        name="Pressure (Surface Level)",
        unit_imperial=PRESSURE_INHG,
        unit_metric=PRESSURE_HPA,
        metric_conversion=lambda val: pressure_convert(
            val, PRESSURE_INHG, PRESSURE_HPA
        ),
        device_class=SensorDeviceClass.PRESSURE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_SOLAR_GHI,
        name="Global Horizontal Irradiance",
        unit_imperial=IRRADIATION_BTUS_PER_HOUR_SQUARE_FOOT,
        unit_metric=IRRADIATION_WATTS_PER_SQUARE_METER,
        metric_conversion=3.15459,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CLOUD_BASE,
        name="Cloud Base",
        unit_imperial=LENGTH_MILES,
        unit_metric=LENGTH_KILOMETERS,
        metric_conversion=lambda val: distance_convert(
            val, LENGTH_MILES, LENGTH_KILOMETERS
        ),
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CLOUD_CEILING,
        name="Cloud Ceiling",
        unit_imperial=LENGTH_MILES,
        unit_metric=LENGTH_KILOMETERS,
        metric_conversion=lambda val: distance_convert(
            val, LENGTH_MILES, LENGTH_KILOMETERS
        ),
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CLOUD_COVER,
        name="Cloud Cover",
        unit_imperial=PERCENTAGE,
        unit_metric=PERCENTAGE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_WIND_GUST,
        name="Wind Gust",
        unit_imperial=SPEED_MILES_PER_HOUR,
        unit_metric=SPEED_METERS_PER_SECOND,
        metric_conversion=lambda val: distance_convert(val, LENGTH_MILES, LENGTH_METERS)
        / 3600,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PRECIPITATION_TYPE,
        name="Precipitation Type",
        value_map=PrecipitationType,
        device_class="tomorrowio__precipitation_type",
        icon="mdi:weather-snowy-rainy",
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_OZONE,
        name="Ozone",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=2.03,
        device_class=SensorDeviceClass.OZONE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PARTICULATE_MATTER_25,
        name="Particulate Matter < 2.5 μm",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=3.2808399**3,
        device_class=SensorDeviceClass.PM25,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PARTICULATE_MATTER_10,
        name="Particulate Matter < 10 μm",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=3.2808399**3,
        device_class=SensorDeviceClass.PM10,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_NITROGEN_DIOXIDE,
        name="Nitrogen Dioxide",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=1.95,
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CARBON_MONOXIDE,
        name="Carbon Monoxide",
        unit_imperial=CONCENTRATION_PARTS_PER_MILLION,
        unit_metric=CONCENTRATION_PARTS_PER_MILLION,
        multiplication_factor=1 / 1000,
        device_class=SensorDeviceClass.CO,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_SULPHUR_DIOXIDE,
        name="Sulphur Dioxide",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=2.71,
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_EPA_AQI,
        name="US EPA Air Quality Index",
        device_class=SensorDeviceClass.AQI,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_EPA_PRIMARY_POLLUTANT,
        name="US EPA Primary Pollutant",
        value_map=PrimaryPollutantType,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_EPA_HEALTH_CONCERN,
        name="US EPA Health Concern",
        value_map=HealthConcernType,
        device_class="tomorrowio__health_concern",
        icon="mdi:hospital",
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CHINA_AQI,
        name="China MEP Air Quality Index",
        device_class=SensorDeviceClass.AQI,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CHINA_PRIMARY_POLLUTANT,
        name="China MEP Primary Pollutant",
        value_map=PrimaryPollutantType,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CHINA_HEALTH_CONCERN,
        name="China MEP Health Concern",
        value_map=HealthConcernType,
        device_class="tomorrowio__health_concern",
        icon="mdi:hospital",
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_POLLEN_TREE,
        name="Tree Pollen Index",
        value_map=PollenIndex,
        device_class="tomorrowio__pollen_index",
        icon="mdi:flower-pollen",
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_POLLEN_WEED,
        name="Weed Pollen Index",
        value_map=PollenIndex,
        device_class="tomorrowio__pollen_index",
        icon="mdi:flower-pollen",
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_POLLEN_GRASS,
        name="Grass Pollen Index",
        value_map=PollenIndex,
        device_class="tomorrowio__pollen_index",
        icon="mdi:flower-pollen",
    ),
    TomorrowioSensorEntityDescription(
        TMRW_ATTR_FIRE_INDEX,
        name="Fire Index",
        icon="mdi:fire",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        TomorrowioSensorEntity(hass, config_entry, coordinator, 4, description)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)


def smart_round(value: float) -> float:
    """Round a float to have at least two digits."""
    if float(value) == 0.0:
        return float(value)

    num_digits = 2
    if (new_val := round(value, num_digits)) != 0.0:
        return new_val

    while num_digits < 5 and (new_val := round(value, num_digits)) == 0.0:
        num_digits += 1

    return new_val


class BaseTomorrowioSensorEntity(TomorrowioEntity, SensorEntity):
    """Base Tomorrow.io sensor entity."""

    entity_description: TomorrowioSensorEntityDescription
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        coordinator: TomorrowioDataUpdateCoordinator,
        api_version: int,
        description: TomorrowioSensorEntityDescription,
    ) -> None:
        """Initialize Tomorrow.io Sensor Entity."""
        super().__init__(config_entry, coordinator, api_version)
        self.entity_description = description
        self._attr_name = f"{self._config_entry.data[CONF_NAME]} - {description.name}"
        self._attr_unique_id = (
            f"{self._config_entry.unique_id}_{slugify(description.name)}"
        )
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: self.attribution}
        # Fallback to metric always in case imperial isn't defined (for metric only
        # sensors)
        self._attr_native_unit_of_measurement = (
            description.unit_metric
            if hass.config.units.is_metric
            else description.unit_imperial
        ) or description.unit_metric

    @property
    @abstractmethod
    def _state(self) -> str | int | float | None:
        """Return the raw state."""

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        state = self._state
        desc = self.entity_description

        if state is None:
            return state

        if desc.value_map is not None:
            return desc.value_map(state).name.lower()

        if desc.multiplication_factor is not None:
            return smart_round(float(state) * desc.multiplication_factor)

        # If an imperial unit isn't provided, we always want to convert to metric since
        # that is what the UI expects
        if (
            desc.metric_conversion
            and desc.unit_imperial is not None
            and desc.unit_imperial != desc.unit_metric
            and self.hass.config.units.is_metric
        ):
            conversion = desc.metric_conversion
            # When conversion is a callable, we assume it's a single input function
            if callable(conversion):
                return smart_round(conversion(float(state)))

            return smart_round(float(state) * conversion)

        return state


class TomorrowioSensorEntity(BaseTomorrowioSensorEntity):
    """Sensor entity that talks to Tomorrow.io v4 API to retrieve non-weather data."""

    @property
    def _state(self) -> str | int | float | None:
        """Return the raw state."""
        return self._get_current_property(self.entity_description.key)
