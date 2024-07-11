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
    UVDescription,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_API_KEY,
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import DistanceConverter, SpeedConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import TomorrowioEntity
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
    TMRW_ATTR_UV_HEALTH_CONCERN,
    TMRW_ATTR_UV_INDEX,
    TMRW_ATTR_WIND_GUST,
)
from .coordinator import TomorrowioDataUpdateCoordinator


@dataclass(frozen=True)
class TomorrowioSensorEntityDescription(SensorEntityDescription):
    """Describes a Tomorrow.io sensor entity."""

    attribute: str = ""
    unit_imperial: str | None = None
    unit_metric: str | None = None
    multiplication_factor: Callable[[float], float] | float | None = None
    imperial_conversion: Callable[[float], float] | float | None = None
    value_map: Any | None = None

    def __post_init__(self) -> None:
        """Handle post init."""
        if (self.unit_imperial is None and self.unit_metric is not None) or (
            self.unit_imperial is not None and self.unit_metric is None
        ):
            raise ValueError(
                "Entity descriptions must include both imperial and metric units or "
                "they must both be None"
            )

        if self.value_map is not None:
            options = [item.name.lower() for item in self.value_map]
            object.__setattr__(self, "device_class", SensorDeviceClass.ENUM)
            object.__setattr__(self, "options", options)


# From https://cfpub.epa.gov/ncer_abstracts/index.cfm/fuseaction/display.files/fileID/14285
# x ug/m^3 = y ppb * molecular weight / 24.45
def convert_ppb_to_ugm3(molecular_weight: float) -> Callable[[float], float]:
    """Return function to convert ppb to ug/m^3."""
    return lambda x: (x * molecular_weight) / 24.45


SENSOR_TYPES = (
    TomorrowioSensorEntityDescription(
        key="feels_like",
        translation_key="feels_like",
        attribute=TMRW_ATTR_FEELS_LIKE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TomorrowioSensorEntityDescription(
        key="dew_point",
        translation_key="dew_point",
        attribute=TMRW_ATTR_DEW_POINT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Data comes in as hPa
    TomorrowioSensorEntityDescription(
        key="pressure_surface_level",
        attribute=TMRW_ATTR_PRESSURE_SURFACE_LEVEL,
        native_unit_of_measurement=UnitOfPressure.HPA,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Data comes in as W/m^2, convert to BTUs/(hr * ft^2) for imperial
    # https://www.theunitconverter.com/watt-square-meter-to-btu-hour-square-foot-conversion/
    TomorrowioSensorEntityDescription(
        key="global_horizontal_irradiance",
        attribute=TMRW_ATTR_SOLAR_GHI,
        unit_imperial=UnitOfIrradiance.BTUS_PER_HOUR_SQUARE_FOOT,
        unit_metric=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        imperial_conversion=(1 / 3.15459),
        device_class=SensorDeviceClass.IRRADIANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Data comes in as km, convert to miles for imperial
    TomorrowioSensorEntityDescription(
        key="cloud_base",
        translation_key="cloud_base",
        attribute=TMRW_ATTR_CLOUD_BASE,
        unit_imperial=UnitOfLength.MILES,
        unit_metric=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_conversion=lambda val: DistanceConverter.convert(
            val,
            UnitOfLength.KILOMETERS,
            UnitOfLength.MILES,
        ),
    ),
    # Data comes in as km, convert to miles for imperial
    TomorrowioSensorEntityDescription(
        key="cloud_ceiling",
        translation_key="cloud_ceiling",
        attribute=TMRW_ATTR_CLOUD_CEILING,
        unit_imperial=UnitOfLength.MILES,
        unit_metric=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_conversion=lambda val: DistanceConverter.convert(
            val,
            UnitOfLength.KILOMETERS,
            UnitOfLength.MILES,
        ),
    ),
    TomorrowioSensorEntityDescription(
        key="cloud_cover",
        translation_key="cloud_cover",
        attribute=TMRW_ATTR_CLOUD_COVER,
        native_unit_of_measurement=PERCENTAGE,
    ),
    # Data comes in as m/s, convert to mi/h for imperial
    TomorrowioSensorEntityDescription(
        key="wind_gust",
        translation_key="wind_gust",
        attribute=TMRW_ATTR_WIND_GUST,
        unit_imperial=UnitOfSpeed.MILES_PER_HOUR,
        unit_metric=UnitOfSpeed.METERS_PER_SECOND,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        imperial_conversion=lambda val: SpeedConverter.convert(
            val, UnitOfSpeed.METERS_PER_SECOND, UnitOfSpeed.MILES_PER_HOUR
        ),
    ),
    TomorrowioSensorEntityDescription(
        key="precipitation_type",
        translation_key="precipitation_type",
        attribute=TMRW_ATTR_PRECIPITATION_TYPE,
        value_map=PrecipitationType,
    ),
    # Data comes in as ppb, convert to µg/m^3
    # Molecular weight of Ozone is 48
    TomorrowioSensorEntityDescription(
        key="ozone",
        attribute=TMRW_ATTR_OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=convert_ppb_to_ugm3(48),
        device_class=SensorDeviceClass.OZONE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TomorrowioSensorEntityDescription(
        key="particulate_matter_2_5_mm",
        attribute=TMRW_ATTR_PARTICULATE_MATTER_25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM25,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TomorrowioSensorEntityDescription(
        key="particulate_matter_10_mm",
        attribute=TMRW_ATTR_PARTICULATE_MATTER_10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        device_class=SensorDeviceClass.PM10,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Data comes in as ppb, convert to µg/m^3
    # Molecular weight of Nitrogen Dioxide is 46.01
    TomorrowioSensorEntityDescription(
        key="nitrogen_dioxide",
        attribute=TMRW_ATTR_NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=convert_ppb_to_ugm3(46.01),
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Data comes in as ppb, convert to ppm
    TomorrowioSensorEntityDescription(
        key="carbon_monoxide",
        attribute=TMRW_ATTR_CARBON_MONOXIDE,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        multiplication_factor=1 / 1000,
        device_class=SensorDeviceClass.CO,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # Data comes in as ppb, convert to µg/m^3
    # Molecular weight of Sulphur Dioxide is 64.07
    TomorrowioSensorEntityDescription(
        key="sulphur_dioxide",
        attribute=TMRW_ATTR_SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        multiplication_factor=convert_ppb_to_ugm3(64.07),
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TomorrowioSensorEntityDescription(
        key="us_epa_air_quality_index",
        translation_key="us_epa_air_quality_index",
        attribute=TMRW_ATTR_EPA_AQI,
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TomorrowioSensorEntityDescription(
        key="us_epa_primary_pollutant",
        translation_key="primary_pollutant",
        attribute=TMRW_ATTR_EPA_PRIMARY_POLLUTANT,
        value_map=PrimaryPollutantType,
    ),
    TomorrowioSensorEntityDescription(
        key="us_epa_health_concern",
        translation_key="health_concern",
        attribute=TMRW_ATTR_EPA_HEALTH_CONCERN,
        value_map=HealthConcernType,
    ),
    TomorrowioSensorEntityDescription(
        key="china_mep_air_quality_index",
        translation_key="china_mep_air_quality_index",
        attribute=TMRW_ATTR_CHINA_AQI,
        device_class=SensorDeviceClass.AQI,
    ),
    TomorrowioSensorEntityDescription(
        key="china_mep_primary_pollutant",
        translation_key="china_mep_primary_pollutant",
        attribute=TMRW_ATTR_CHINA_PRIMARY_POLLUTANT,
        value_map=PrimaryPollutantType,
    ),
    TomorrowioSensorEntityDescription(
        key="china_mep_health_concern",
        translation_key="china_mep_health_concern",
        attribute=TMRW_ATTR_CHINA_HEALTH_CONCERN,
        value_map=HealthConcernType,
    ),
    TomorrowioSensorEntityDescription(
        key="tree_pollen_index",
        translation_key="pollen_index",
        attribute=TMRW_ATTR_POLLEN_TREE,
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        key="weed_pollen_index",
        translation_key="weed_pollen_index",
        attribute=TMRW_ATTR_POLLEN_WEED,
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        key="grass_pollen_index",
        translation_key="grass_pollen_index",
        attribute=TMRW_ATTR_POLLEN_GRASS,
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        key="fire_index",
        translation_key="fire_index",
        attribute=TMRW_ATTR_FIRE_INDEX,
    ),
    TomorrowioSensorEntityDescription(
        key="uv_index",
        translation_key="uv_index",
        attribute=TMRW_ATTR_UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    TomorrowioSensorEntityDescription(
        key="uv_radiation_health_concern",
        translation_key="uv_radiation_health_concern",
        attribute=TMRW_ATTR_UV_HEALTH_CONCERN,
        value_map=UVDescription,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.data[CONF_API_KEY]]
    entities = [
        TomorrowioSensorEntity(hass, config_entry, coordinator, 4, description)
        for description in SENSOR_TYPES
    ]
    async_add_entities(entities)


def handle_conversion(
    value: float, conversion: Callable[[float], float] | float
) -> float:
    """Handle conversion of a value based on conversion type."""
    if callable(conversion):
        return round(conversion(float(value)), 2)

    return round(float(value) * conversion, 2)


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
        self._attr_unique_id = f"{self._config_entry.unique_id}_{description.key}"
        if self.entity_description.native_unit_of_measurement is None:
            self._attr_native_unit_of_measurement = description.unit_metric
            if hass.config.units is US_CUSTOMARY_SYSTEM:
                self._attr_native_unit_of_measurement = description.unit_imperial

    @property
    @abstractmethod
    def _state(self) -> int | float | None:
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
            state = handle_conversion(state, desc.multiplication_factor)

        # If there is an imperial conversion needed and the instance is using imperial,
        # apply the conversion logic.
        if (
            desc.imperial_conversion
            and desc.unit_imperial is not None
            and desc.unit_imperial != desc.unit_metric
            and self.hass.config.units is US_CUSTOMARY_SYSTEM
        ):
            return handle_conversion(state, desc.imperial_conversion)

        return state


class TomorrowioSensorEntity(BaseTomorrowioSensorEntity):
    """Sensor entity that talks to Tomorrow.io v4 API to retrieve non-weather data."""

    @property
    def _state(self) -> int | float | None:
        """Return the raw state."""
        val = self._get_current_property(self.entity_description.attribute)
        assert not isinstance(val, str)
        return val
