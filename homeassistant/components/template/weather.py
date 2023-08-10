"""Template platform that aggregates meteorological data."""
from __future__ import annotations

from functools import partial
from typing import Literal

import voluptuous as vol

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ENTITY_ID_FORMAT,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import CONF_NAME, CONF_TEMPERATURE_UNIT, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .template_entity import TemplateEntity, rewrite_common_legacy_to_modern_conf

CHECK_FORECAST_KEYS = set().union(Forecast.__annotations__.keys())

CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_CONDITION_EXCEPTIONAL,
}

CONF_WEATHER = "weather"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_HUMIDITY_TEMPLATE = "humidity_template"
CONF_CONDITION_TEMPLATE = "condition_template"
CONF_ATTRIBUTION_TEMPLATE = "attribution_template"
CONF_PRESSURE_TEMPLATE = "pressure_template"
CONF_WIND_SPEED_TEMPLATE = "wind_speed_template"
CONF_WIND_BEARING_TEMPLATE = "wind_bearing_template"
CONF_OZONE_TEMPLATE = "ozone_template"
CONF_VISIBILITY_TEMPLATE = "visibility_template"
CONF_FORECAST_TEMPLATE = "forecast_template"
CONF_FORECAST_DAILY_TEMPLATE = "forecast_daily_template"
CONF_FORECAST_HOURLY_TEMPLATE = "forecast_hourly_template"
CONF_FORECAST_TWICE_DAILY_TEMPLATE = "forecast_twice_daily_template"
CONF_PRESSURE_UNIT = "pressure_unit"
CONF_WIND_SPEED_UNIT = "wind_speed_unit"
CONF_VISIBILITY_UNIT = "visibility_unit"
CONF_PRECIPITATION_UNIT = "precipitation_unit"
CONF_WIND_GUST_SPEED_TEMPLATE = "wind_gust_speed_template"
CONF_CLOUD_COVERAGE_TEMPLATE = "cloud_coverage_template"
CONF_DEW_POINT_TEMPLATE = "dew_point_template"
CONF_APPARENT_TEMPERATURE_TEMPLATE = "apparent_temperature_template"

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_FORECAST_TEMPLATE),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_CONDITION_TEMPLATE): cv.template,
            vol.Required(CONF_TEMPERATURE_TEMPLATE): cv.template,
            vol.Required(CONF_HUMIDITY_TEMPLATE): cv.template,
            vol.Optional(CONF_ATTRIBUTION_TEMPLATE): cv.template,
            vol.Optional(CONF_PRESSURE_TEMPLATE): cv.template,
            vol.Optional(CONF_WIND_SPEED_TEMPLATE): cv.template,
            vol.Optional(CONF_WIND_BEARING_TEMPLATE): cv.template,
            vol.Optional(CONF_OZONE_TEMPLATE): cv.template,
            vol.Optional(CONF_VISIBILITY_TEMPLATE): cv.template,
            vol.Optional(CONF_FORECAST_TEMPLATE): cv.template,
            vol.Optional(CONF_FORECAST_DAILY_TEMPLATE): cv.template,
            vol.Optional(CONF_FORECAST_HOURLY_TEMPLATE): cv.template,
            vol.Optional(CONF_FORECAST_TWICE_DAILY_TEMPLATE): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
            vol.Optional(CONF_TEMPERATURE_UNIT): vol.In(
                TemperatureConverter.VALID_UNITS
            ),
            vol.Optional(CONF_PRESSURE_UNIT): vol.In(PressureConverter.VALID_UNITS),
            vol.Optional(CONF_WIND_SPEED_UNIT): vol.In(SpeedConverter.VALID_UNITS),
            vol.Optional(CONF_VISIBILITY_UNIT): vol.In(DistanceConverter.VALID_UNITS),
            vol.Optional(CONF_PRECIPITATION_UNIT): vol.In(
                DistanceConverter.VALID_UNITS
            ),
            vol.Optional(CONF_WIND_GUST_SPEED_TEMPLATE): cv.template,
            vol.Optional(CONF_CLOUD_COVERAGE_TEMPLATE): cv.template,
            vol.Optional(CONF_DEW_POINT_TEMPLATE): cv.template,
            vol.Optional(CONF_APPARENT_TEMPERATURE_TEMPLATE): cv.template,
        }
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template weather."""

    config = rewrite_common_legacy_to_modern_conf(config)
    unique_id = config.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            WeatherTemplate(
                hass,
                config,
                unique_id,
            )
        ]
    )


class WeatherTemplate(TemplateEntity, WeatherEntity):
    """Representation of a weather condition."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the Template weather."""
        super().__init__(hass, config=config, unique_id=unique_id)

        name = self._attr_name
        self._condition_template = config[CONF_CONDITION_TEMPLATE]
        self._temperature_template = config[CONF_TEMPERATURE_TEMPLATE]
        self._humidity_template = config[CONF_HUMIDITY_TEMPLATE]
        self._attribution_template = config.get(CONF_ATTRIBUTION_TEMPLATE)
        self._pressure_template = config.get(CONF_PRESSURE_TEMPLATE)
        self._wind_speed_template = config.get(CONF_WIND_SPEED_TEMPLATE)
        self._wind_bearing_template = config.get(CONF_WIND_BEARING_TEMPLATE)
        self._ozone_template = config.get(CONF_OZONE_TEMPLATE)
        self._visibility_template = config.get(CONF_VISIBILITY_TEMPLATE)
        self._forecast_template = config.get(CONF_FORECAST_TEMPLATE)
        self._forecast_daily_template = config.get(CONF_FORECAST_DAILY_TEMPLATE)
        self._forecast_hourly_template = config.get(CONF_FORECAST_HOURLY_TEMPLATE)
        self._forecast_twice_daily_template = config.get(
            CONF_FORECAST_TWICE_DAILY_TEMPLATE
        )
        self._wind_gust_speed_template = config.get(CONF_WIND_GUST_SPEED_TEMPLATE)
        self._cloud_coverage_template = config.get(CONF_CLOUD_COVERAGE_TEMPLATE)
        self._dew_point_template = config.get(CONF_DEW_POINT_TEMPLATE)
        self._apparent_temperature_template = config.get(
            CONF_APPARENT_TEMPERATURE_TEMPLATE
        )

        self._attr_native_precipitation_unit = config.get(CONF_PRECIPITATION_UNIT)
        self._attr_native_pressure_unit = config.get(CONF_PRESSURE_UNIT)
        self._attr_native_temperature_unit = config.get(CONF_TEMPERATURE_UNIT)
        self._attr_native_visibility_unit = config.get(CONF_VISIBILITY_UNIT)
        self._attr_native_wind_speed_unit = config.get(CONF_WIND_SPEED_UNIT)

        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, name, hass=hass)

        self._condition = None
        self._temperature = None
        self._humidity = None
        self._attribution = None
        self._pressure = None
        self._wind_speed = None
        self._wind_bearing = None
        self._ozone = None
        self._visibility = None
        self._wind_gust_speed = None
        self._cloud_coverage = None
        self._dew_point = None
        self._apparent_temperature = None
        self._forecast: list[Forecast] = []
        self._forecast_daily: list[Forecast] = []
        self._forecast_hourly: list[Forecast] = []
        self._forecast_twice_daily: list[Forecast] = []

        self._attr_supported_features = 0
        if self._forecast_daily_template:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_DAILY
        if self._forecast_hourly_template:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_HOURLY
        if self._forecast_twice_daily_template:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_TWICE_DAILY

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self._condition

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self._temperature

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self._humidity

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self._wind_speed

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._wind_bearing

    @property
    def ozone(self) -> float | None:
        """Return the ozone level."""
        return self._ozone

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self._visibility

    @property
    def native_pressure(self) -> float | None:
        """Return the air pressure."""
        return self._pressure

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return self._wind_gust_speed

    @property
    def cloud_coverage(self) -> float | None:
        """Return the cloud coverage."""
        return self._cloud_coverage

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return self._dew_point

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self._apparent_temperature

    @property
    def forecast(self) -> list[Forecast]:
        """Return the forecast."""
        return self._forecast

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_daily

    async def async_forecast_hourly(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_hourly

    async def async_forecast_twice_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_twice_daily

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        if self._attribution is None:
            return "Powered by Home Assistant"
        return self._attribution

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        if self._condition_template:
            self.add_template_attribute(
                "_condition",
                self._condition_template,
                lambda condition: condition if condition in CONDITION_CLASSES else None,
            )
        if self._temperature_template:
            self.add_template_attribute(
                "_temperature",
                self._temperature_template,
            )
        if self._humidity_template:
            self.add_template_attribute(
                "_humidity",
                self._humidity_template,
            )
        if self._attribution_template:
            self.add_template_attribute(
                "_attribution",
                self._attribution_template,
            )
        if self._pressure_template:
            self.add_template_attribute(
                "_pressure",
                self._pressure_template,
            )
        if self._wind_speed_template:
            self.add_template_attribute(
                "_wind_speed",
                self._wind_speed_template,
            )
        if self._wind_bearing_template:
            self.add_template_attribute(
                "_wind_bearing",
                self._wind_bearing_template,
            )
        if self._ozone_template:
            self.add_template_attribute(
                "_ozone",
                self._ozone_template,
            )
        if self._visibility_template:
            self.add_template_attribute(
                "_visibility",
                self._visibility_template,
            )
        if self._wind_gust_speed_template:
            self.add_template_attribute(
                "_wind_gust_speed",
                self._wind_gust_speed_template,
            )
        if self._cloud_coverage_template:
            self.add_template_attribute(
                "_cloud_coverage",
                self._cloud_coverage_template,
            )
        if self._dew_point_template:
            self.add_template_attribute(
                "_dew_point",
                self._dew_point_template,
            )
        if self._apparent_temperature_template:
            self.add_template_attribute(
                "_apparent_temperature",
                self._apparent_temperature_template,
            )
        if self._forecast_template:
            self.add_template_attribute(
                "_forecast",
                self._forecast_template,
            )

        if self._forecast_daily_template:
            self.add_template_attribute(
                "_forecast_daily",
                self._forecast_daily_template,
                on_update=partial(self._update_forecast, "daily"),
                validator=partial(self._validate_forecast, "daily"),
            )
        if self._forecast_hourly_template:
            self.add_template_attribute(
                "_forecast_hourly",
                self._forecast_hourly_template,
                on_update=partial(self._update_forecast, "hourly"),
                validator=partial(self._validate_forecast, "hourly"),
            )
        if self._forecast_twice_daily_template:
            self.add_template_attribute(
                "_forecast_twice_daily",
                self._forecast_twice_daily_template,
                on_update=partial(self._update_forecast, "twice_daily"),
                validator=partial(self._validate_forecast, "twice_daily"),
            )

        await super().async_added_to_hass()

    @callback
    def _update_forecast(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
        result: list[Forecast] | TemplateError,
    ) -> None:
        """Save template result and trigger forecast listener."""
        attr_result = None if isinstance(result, TemplateError) else result
        setattr(self, f"_forecast_{forecast_type}", attr_result)
        self.hass.create_task(self.async_update_listeners([forecast_type]))

    @callback
    def _validate_forecast(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
        result: list[Forecast] | TemplateError,
    ) -> list[Forecast] | None:
        """Validate the forecasts."""
        if result is None or isinstance(result, TemplateError):
            return None

        if isinstance(result, list):
            for forecast in result:
                diff_result = (
                    set().union(forecast.keys()).difference(CHECK_FORECAST_KEYS)
                )
                if diff_result:
                    raise vol.Invalid(
                        "Only valid keys in Forecast are allowed, see Weather documentation https://www.home-assistant.io/integrations/weather/"
                    )
                if (
                    forecast_type == "twice_daily"
                    and "is_daytime" not in forecast.keys()
                ):
                    raise vol.Invalid(
                        "`is_daytime` is missing in twice_daily forecast, see Weather documentation https://www.home-assistant.io/integrations/weather/"
                    )
                if "datetime" not in forecast.keys():
                    raise vol.Invalid(
                        "`datetime` is required in forecasts, see Weather documentation https://www.home-assistant.io/integrations/weather/"
                    )
                continue
        return result
