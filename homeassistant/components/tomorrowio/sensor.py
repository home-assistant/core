"""Sensor component that handles additional Tomorrowio data for your location."""
from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
import logging
from typing import Any, Callable

from pytomorrowio.const import (
    HealthConcernType,
    PollenIndex,
    PrecipitationType,
    PrimaryPollutantType,
)

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_NAME,
    DEVICE_CLASS_AQI,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_NITROGEN_DIOXIDE,
    DEVICE_CLASS_OZONE,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SULPHUR_DIOXIDE,
    DEVICE_CLASS_TEMPERATURE,
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

_LOGGER = logging.getLogger(__name__)


@dataclass
class TomorrowioSensorEntityDescription(SensorEntityDescription):
    """Describes a Tomorrow.io sensor entity."""

    unit_imperial: str | None = None
    unit_metric: str | None = None
    metric_conversion: Callable[[float], float] | float = 1.0
    is_metric_check: bool | None = None
    value_map: Any | None = None


SENSOR_TYPES = (
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_FEELS_LIKE,
        name="Feels Like",
        unit_imperial=TEMP_FAHRENHEIT,
        unit_metric=TEMP_CELSIUS,
        metric_conversion=lambda val: temp_convert(val, TEMP_FAHRENHEIT, TEMP_CELSIUS),
        is_metric_check=True,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_DEW_POINT,
        name="Dew Point",
        unit_imperial=TEMP_FAHRENHEIT,
        unit_metric=TEMP_CELSIUS,
        metric_conversion=lambda val: temp_convert(val, TEMP_FAHRENHEIT, TEMP_CELSIUS),
        is_metric_check=True,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PRESSURE_SURFACE_LEVEL,
        name="Pressure (Surface Level)",
        unit_metric=PRESSURE_HPA,
        metric_conversion=lambda val: pressure_convert(
            val, PRESSURE_INHG, PRESSURE_HPA
        ),
        is_metric_check=True,
        device_class=DEVICE_CLASS_PRESSURE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_SOLAR_GHI,
        name="Global Horizontal Irradiance",
        unit_imperial=IRRADIATION_BTUS_PER_HOUR_SQUARE_FOOT,
        unit_metric=IRRADIATION_WATTS_PER_SQUARE_METER,
        metric_conversion=3.15459,
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CLOUD_BASE,
        name="Cloud Base",
        unit_imperial=LENGTH_MILES,
        unit_metric=LENGTH_KILOMETERS,
        metric_conversion=lambda val: distance_convert(
            val, LENGTH_MILES, LENGTH_KILOMETERS
        ),
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CLOUD_CEILING,
        name="Cloud Ceiling",
        unit_imperial=LENGTH_MILES,
        unit_metric=LENGTH_KILOMETERS,
        metric_conversion=lambda val: distance_convert(
            val, LENGTH_MILES, LENGTH_KILOMETERS
        ),
        is_metric_check=True,
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
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PRECIPITATION_TYPE,
        name="Precipitation Type",
        value_map=PrecipitationType,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_OZONE,
        name="Ozone",
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=2.03,
        is_metric_check=True,
        device_class=DEVICE_CLASS_OZONE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PARTICULATE_MATTER_25,
        name="Particulate Matter < 2.5 μm",
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=3.2808399 ** 3,
        is_metric_check=True,
        device_class=DEVICE_CLASS_PM25,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_PARTICULATE_MATTER_10,
        name="Particulate Matter < 10 μm",
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=3.2808399 ** 3,
        is_metric_check=True,
        device_class=DEVICE_CLASS_PM10,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_NITROGEN_DIOXIDE,
        name="Nitrogen Dioxide",
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=1.95,
        is_metric_check=True,
        device_class=DEVICE_CLASS_NITROGEN_DIOXIDE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CARBON_MONOXIDE,
        name="Carbon Monoxide",
        unit_imperial=CONCENTRATION_PARTS_PER_MILLION,
        unit_metric=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_SULPHUR_DIOXIDE,
        name="Sulphur Dioxide",
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=2.71,
        is_metric_check=True,
        device_class=DEVICE_CLASS_SULPHUR_DIOXIDE,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_EPA_AQI,
        name="US EPA Air Quality Index",
        device_class=DEVICE_CLASS_AQI,
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
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_CHINA_AQI,
        name="China MEP Air Quality Index",
        device_class=DEVICE_CLASS_AQI,
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
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_POLLEN_TREE,
        name="Tree Pollen Index",
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_POLLEN_WEED,
        name="Weed Pollen Index",
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        key=TMRW_ATTR_POLLEN_GRASS,
        name="Grass Pollen Index",
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        TMRW_ATTR_FIRE_INDEX,
        name="Fire Index",
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

        # If an imperial unit isn't provided, we always want to convert to metric since
        # that is what the UI expects
        if state is not None and (
            (
                self.entity_description.metric_conversion != 1.0
                and self.entity_description.is_metric_check is not None
                and self.hass.config.units.is_metric
                == self.entity_description.is_metric_check
            )
            or (
                self.entity_description.unit_imperial is None
                and self.entity_description.unit_metric is not None
            )
        ):
            conversion = self.entity_description.metric_conversion
            # When conversion is a callable, we assume it's a single input function
            if callable(conversion):
                return round(conversion(float(state)), 2)

            return round(float(state) * conversion, 2)

        if self.entity_description.value_map is not None and state is not None:
            return self.entity_description.value_map(state).name.lower()

        return state


class TomorrowioSensorEntity(BaseTomorrowioSensorEntity):
    """Sensor entity that talks to Tomorrow.io v4 API to retrieve non-weather data."""

    @property
    def _state(self) -> str | int | float | None:
        """Return the raw state."""
        return self._get_current_property(self.entity_description.key)
