"""Template platform that aggregates meteorological data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Literal, Self

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
    DOMAIN as WEATHER_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as WEATHER_PLATFORM_SCHEMA,
    Forecast,
    WeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_TEMPERATURE_UNIT,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .coordinator import TriggerUpdateCoordinator
from .entity import AbstractTemplateEntity
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
    rewrite_legacy_to_modern_config,
)
from .schemas import (
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_modern_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

CHECK_FORECAST_KEYS = (
    set()
    .union(Forecast.__annotations__.keys())
    # Manually add the forecast resulting attributes that only exists
    #  as native_* in the Forecast definition
    .union(("apparent_temperature", "wind_gust_speed", "dew_point"))
)

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

CONF_APPARENT_TEMPERATURE = "apparent_temperature"
CONF_APPARENT_TEMPERATURE_TEMPLATE = "apparent_temperature_template"
CONF_ATTRIBUTION = "attribution"
CONF_ATTRIBUTION_TEMPLATE = "attribution_template"
CONF_CLOUD_COVERAGE = "cloud_coverage"
CONF_CLOUD_COVERAGE_TEMPLATE = "cloud_coverage_template"
CONF_CONDITION = "condition"
CONF_CONDITION_TEMPLATE = "condition_template"
CONF_DEW_POINT = "dew_point"
CONF_DEW_POINT_TEMPLATE = "dew_point_template"
CONF_FORECAST_DAILY = "forecast_daily"
CONF_FORECAST_DAILY_TEMPLATE = "forecast_daily_template"
CONF_FORECAST_HOURLY = "forecast_hourly"
CONF_FORECAST_HOURLY_TEMPLATE = "forecast_hourly_template"
CONF_FORECAST_TWICE_DAILY = "forecast_twice_daily"
CONF_FORECAST_TWICE_DAILY_TEMPLATE = "forecast_twice_daily_template"
CONF_HUMIDITY = "humidity"
CONF_HUMIDITY_TEMPLATE = "humidity_template"
CONF_OZONE = "ozone"
CONF_OZONE_TEMPLATE = "ozone_template"
CONF_PRECIPITATION_UNIT = "precipitation_unit"
CONF_PRESSURE = "pressure"
CONF_PRESSURE_TEMPLATE = "pressure_template"
CONF_PRESSURE_UNIT = "pressure_unit"
CONF_TEMPERATURE = "temperature"
CONF_TEMPERATURE_TEMPLATE = "temperature_template"
CONF_UV_INDEX = "uv_index"
CONF_UV_INDEX_TEMPLATE = "uv_index_template"
CONF_VISIBILITY = "visibility"
CONF_VISIBILITY_TEMPLATE = "visibility_template"
CONF_VISIBILITY_UNIT = "visibility_unit"
CONF_WEATHER = "weather"
CONF_WIND_BEARING = "wind_bearing"
CONF_WIND_BEARING_TEMPLATE = "wind_bearing_template"
CONF_WIND_GUST_SPEED = "wind_gust_speed"
CONF_WIND_GUST_SPEED_TEMPLATE = "wind_gust_speed_template"
CONF_WIND_SPEED = "wind_speed"
CONF_WIND_SPEED_TEMPLATE = "wind_speed_template"
CONF_WIND_SPEED_UNIT = "wind_speed_unit"

DEFAULT_NAME = "Template Weather"

LEGACY_FIELDS = {
    CONF_APPARENT_TEMPERATURE_TEMPLATE: CONF_APPARENT_TEMPERATURE,
    CONF_ATTRIBUTION_TEMPLATE: CONF_ATTRIBUTION,
    CONF_CLOUD_COVERAGE_TEMPLATE: CONF_CLOUD_COVERAGE,
    CONF_CONDITION_TEMPLATE: CONF_CONDITION,
    CONF_DEW_POINT_TEMPLATE: CONF_DEW_POINT,
    CONF_FORECAST_DAILY_TEMPLATE: CONF_FORECAST_DAILY,
    CONF_FORECAST_HOURLY_TEMPLATE: CONF_FORECAST_HOURLY,
    CONF_FORECAST_TWICE_DAILY_TEMPLATE: CONF_FORECAST_TWICE_DAILY,
    CONF_HUMIDITY_TEMPLATE: CONF_HUMIDITY,
    CONF_OZONE_TEMPLATE: CONF_OZONE,
    CONF_PRESSURE_TEMPLATE: CONF_PRESSURE,
    CONF_TEMPERATURE_TEMPLATE: CONF_TEMPERATURE,
    CONF_UV_INDEX_TEMPLATE: CONF_UV_INDEX,
    CONF_VISIBILITY_TEMPLATE: CONF_VISIBILITY,
    CONF_WIND_BEARING_TEMPLATE: CONF_WIND_BEARING,
    CONF_WIND_GUST_SPEED_TEMPLATE: CONF_WIND_GUST_SPEED,
    CONF_WIND_SPEED_TEMPLATE: CONF_WIND_SPEED,
}


WEATHER_COMMON_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_APPARENT_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_ATTRIBUTION_TEMPLATE): cv.template,
        vol.Optional(CONF_CLOUD_COVERAGE_TEMPLATE): cv.template,
        vol.Required(CONF_CONDITION_TEMPLATE): cv.template,
        vol.Optional(CONF_DEW_POINT_TEMPLATE): cv.template,
        vol.Optional(CONF_FORECAST_DAILY_TEMPLATE): cv.template,
        vol.Optional(CONF_FORECAST_HOURLY_TEMPLATE): cv.template,
        vol.Optional(CONF_FORECAST_TWICE_DAILY_TEMPLATE): cv.template,
        vol.Required(CONF_HUMIDITY_TEMPLATE): cv.template,
        vol.Optional(CONF_OZONE_TEMPLATE): cv.template,
        vol.Optional(CONF_PRECIPITATION_UNIT): vol.In(DistanceConverter.VALID_UNITS),
        vol.Optional(CONF_PRESSURE_TEMPLATE): cv.template,
        vol.Optional(CONF_PRESSURE_UNIT): vol.In(PressureConverter.VALID_UNITS),
        vol.Required(CONF_TEMPERATURE_TEMPLATE): cv.template,
        vol.Optional(CONF_TEMPERATURE_UNIT): vol.In(TemperatureConverter.VALID_UNITS),
        vol.Optional(CONF_VISIBILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_VISIBILITY_UNIT): vol.In(DistanceConverter.VALID_UNITS),
        vol.Optional(CONF_WIND_BEARING_TEMPLATE): cv.template,
        vol.Optional(CONF_WIND_GUST_SPEED_TEMPLATE): cv.template,
        vol.Optional(CONF_WIND_SPEED_TEMPLATE): cv.template,
        vol.Optional(CONF_WIND_SPEED_UNIT): vol.In(SpeedConverter.VALID_UNITS),
    }
)


WEATHER_YAML_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_UV_INDEX_TEMPLATE): cv.template,
        }
    )
    .extend(WEATHER_COMMON_SCHEMA.schema)
    .extend(
        make_template_entity_common_modern_schema(WEATHER_DOMAIN, DEFAULT_NAME).schema
    )
)

PLATFORM_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(WEATHER_COMMON_SCHEMA.schema)
    .extend(WEATHER_PLATFORM_SCHEMA.schema)
)


WEATHER_CONFIG_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_APPARENT_TEMPERATURE): cv.template,
        vol.Optional(CONF_ATTRIBUTION): cv.template,
        vol.Optional(CONF_CLOUD_COVERAGE): cv.template,
        vol.Required(CONF_CONDITION): cv.template,
        vol.Optional(CONF_DEW_POINT): cv.template,
        vol.Optional(CONF_FORECAST_DAILY): cv.template,
        vol.Optional(CONF_FORECAST_HOURLY): cv.template,
        vol.Optional(CONF_FORECAST_TWICE_DAILY): cv.template,
        vol.Required(CONF_HUMIDITY): cv.template,
        vol.Optional(CONF_OZONE): cv.template,
        vol.Optional(CONF_PRECIPITATION_UNIT): vol.In(DistanceConverter.VALID_UNITS),
        vol.Optional(CONF_PRESSURE): cv.template,
        vol.Optional(CONF_PRESSURE_UNIT): vol.In(PressureConverter.VALID_UNITS),
        vol.Required(CONF_TEMPERATURE): cv.template,
        vol.Optional(CONF_TEMPERATURE_UNIT): vol.In(TemperatureConverter.VALID_UNITS),
        vol.Optional(CONF_UV_INDEX): cv.template,
        vol.Optional(CONF_VISIBILITY): cv.template,
        vol.Optional(CONF_VISIBILITY_UNIT): vol.In(DistanceConverter.VALID_UNITS),
        vol.Optional(CONF_WIND_BEARING): cv.template,
        vol.Optional(CONF_WIND_GUST_SPEED): cv.template,
        vol.Optional(CONF_WIND_SPEED): cv.template,
        vol.Optional(CONF_WIND_SPEED_UNIT): vol.In(SpeedConverter.VALID_UNITS),
    }
).extend(TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Template weather."""

    # Rewrite the configuration options to modern keys.
    if discovery_info is None:
        # Legacy
        config = rewrite_legacy_to_modern_config(hass, config, LEGACY_FIELDS)
    else:
        # Modern and Trigger
        entity_configs: list[ConfigType] = discovery_info["entities"]
        modified_entity_configs = []
        for entity_config in entity_configs:
            entity_config = rewrite_legacy_to_modern_config(
                hass, entity_config, LEGACY_FIELDS
            )

            modified_entity_configs.append(entity_config)

        if modified_entity_configs:
            discovery_info["entities"] = modified_entity_configs

    await async_setup_template_platform(
        hass,
        WEATHER_DOMAIN,
        config,
        StateWeatherEntity,
        TriggerWeatherEntity,
        async_add_entities,
        discovery_info,
        {},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateWeatherEntity,
        WEATHER_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_weather(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateWeatherEntity:
    """Create a preview."""
    return async_setup_template_preview(
        hass,
        name,
        config,
        StateWeatherEntity,
        WEATHER_CONFIG_ENTRY_SCHEMA,
    )


class AbstractTemplateWeather(AbstractTemplateEntity, WeatherEntity):
    """Representation of a template weathers features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(  # pylint: disable=super-init-not-called
        self, config: dict[str, Any], initial_state: bool | None = False
    ) -> None:
        """Initialize the features."""

        # Templates
        self._apparent_temperature_template = config.get(CONF_APPARENT_TEMPERATURE)
        self._attribution_template = config.get(CONF_ATTRIBUTION)
        self._cloud_coverage_template = config.get(CONF_CLOUD_COVERAGE)
        self._condition_template = config[CONF_CONDITION]
        self._dew_point_template = config.get(CONF_DEW_POINT)
        self._forecast_daily_template = config.get(CONF_FORECAST_DAILY)
        self._forecast_hourly_template = config.get(CONF_FORECAST_HOURLY)
        self._forecast_twice_daily_template = config.get(CONF_FORECAST_TWICE_DAILY)
        self._humidity_template = config[CONF_HUMIDITY]
        self._ozone_template = config.get(CONF_OZONE)
        self._pressure_template = config.get(CONF_PRESSURE)
        self._temperature_template = config[CONF_TEMPERATURE]
        self._uv_index_template = config.get(CONF_UV_INDEX)
        self._visibility_template = config.get(CONF_VISIBILITY)
        self._wind_bearing_template = config.get(CONF_WIND_BEARING)
        self._wind_gust_speed_template = config.get(CONF_WIND_GUST_SPEED)
        self._wind_speed_template = config.get(CONF_WIND_SPEED)

        # Legacy support
        self._attribution: str | None = None

        # Native units
        self._attr_native_precipitation_unit = config.get(CONF_PRECIPITATION_UNIT)
        self._attr_native_pressure_unit = config.get(CONF_PRESSURE_UNIT)
        self._attr_native_temperature_unit = config.get(CONF_TEMPERATURE_UNIT)
        self._attr_native_visibility_unit = config.get(CONF_VISIBILITY_UNIT)
        self._attr_native_wind_speed_unit = config.get(CONF_WIND_SPEED_UNIT)

        # Supported Features
        self._attr_supported_features = 0
        if self._forecast_daily_template:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_DAILY
        if self._forecast_hourly_template:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_HOURLY
        if self._forecast_twice_daily_template:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_TWICE_DAILY

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        if self._attribution is None:
            return "Powered by Home Assistant"
        return self._attribution

    def _validate[T](
        self,
        validator: Callable[[Any], T],
        result: Any,
    ) -> T | None:
        try:
            return validator(result)
        except vol.Invalid:
            return None

    @callback
    def _update_apparent_temperature(self, result: Any) -> None:
        self._attr_native_apparent_temperature = self._validate(
            vol.Coerce(float), result
        )

    @callback
    def _update_attribution(self, result: Any) -> None:
        self._attribution = vol.Coerce(str)(result)

    @callback
    def _update_condition(self, result: Any) -> None:
        self._attr_condition = result if result in CONDITION_CLASSES else None

    @callback
    def _update_coverage(self, result: Any) -> None:
        self._attr_cloud_coverage = self._validate(vol.Coerce(float), result)

    @callback
    def _update_dew_point(self, result: Any) -> None:
        self._attr_native_dew_point = self._validate(vol.Coerce(float), result)

    @callback
    def _update_humidity(self, result: Any) -> None:
        self._attr_humidity = self._validate(vol.Coerce(float), result)

    @callback
    def _update_ozone(self, result: Any) -> None:
        self._attr_ozone = self._validate(vol.Coerce(float), result)

    @callback
    def _update_pressure(self, result: Any) -> None:
        self._attr_native_pressure = self._validate(vol.Coerce(float), result)

    @callback
    def _update_temperature(self, result: Any) -> None:
        self._attr_native_temperature = self._validate(vol.Coerce(float), result)

    @callback
    def _update_uv_index(self, result: Any) -> None:
        self._attr_uv_index = self._validate(vol.Coerce(float), result)

    @callback
    def _update_visibility(self, result: Any) -> None:
        self._attr_native_visibility = self._validate(vol.Coerce(float), result)

    @callback
    def _update_wind_bearing(self, result: Any) -> None:
        try:
            self._attr_wind_bearing = vol.Coerce(float)(result)
        except vol.Invalid:
            self._attr_wind_bearing = vol.Coerce(str)(result)

    @callback
    def _update_wind_gust_speed(self, result: Any) -> None:
        self._attr_native_wind_gust_speed = self._validate(vol.Coerce(float), result)

    @callback
    def _update_wind_speed(self, result: Any) -> None:
        self._attr_native_wind_speed = self._validate(vol.Coerce(float), result)

    @callback
    def _validate_forecast(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
        result: Any,
    ) -> list[Forecast] | None:
        """Validate the forecasts."""
        if result is None:
            return None

        if not isinstance(result, list):
            raise vol.Invalid(
                "Forecasts is not a list, see Weather documentation https://www.home-assistant.io/integrations/weather/"
            )
        for forecast in result:
            if not isinstance(forecast, dict):
                raise vol.Invalid(
                    "Forecast in list is not a dict, see Weather documentation https://www.home-assistant.io/integrations/weather/"
                )
            diff_result = set().union(forecast.keys()).difference(CHECK_FORECAST_KEYS)
            if diff_result:
                raise vol.Invalid(
                    f"Only valid keys in Forecast are allowed, unallowed keys: ({diff_result}), "
                    "see Weather documentation https://www.home-assistant.io/integrations/weather/"
                )
            if forecast_type == "twice_daily" and "is_daytime" not in forecast:
                raise vol.Invalid(
                    "`is_daytime` is missing in twice_daily forecast, see Weather documentation https://www.home-assistant.io/integrations/weather/"
                )
            if "datetime" not in forecast:
                raise vol.Invalid(
                    "`datetime` is required in forecasts, see Weather documentation https://www.home-assistant.io/integrations/weather/"
                )
            continue
        return result


class StateWeatherEntity(TemplateEntity, AbstractTemplateWeather):
    """Representation of a Template weather."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        unique_id: str | None,
    ) -> None:
        """Initialize the Template weather."""
        TemplateEntity.__init__(self, hass, config, unique_id)
        AbstractTemplateWeather.__init__(self, config)

        name = self._attr_name
        if TYPE_CHECKING:
            assert name is not None

        # Forecasts
        self._forecast_daily: list[Forecast] | None = []
        self._forecast_hourly: list[Forecast] | None = []
        self._forecast_twice_daily: list[Forecast] | None = []

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""

        if self._apparent_temperature_template:
            self.add_template_attribute(
                "_attr_native_apparent_temperature",
                self._apparent_temperature_template,
                on_update=self._update_apparent_temperature,
            )
        if self._attribution_template:
            self.add_template_attribute(
                "_attribution",
                self._attribution_template,
                on_update=self._update_attribution,
            )
        if self._cloud_coverage_template:
            self.add_template_attribute(
                "_attr_cloud_coverage",
                self._cloud_coverage_template,
                on_update=self._update_coverage,
            )
        if self._condition_template:
            self.add_template_attribute(
                "_attr_condition",
                self._condition_template,
                on_update=self._update_condition,
            )
        if self._dew_point_template:
            self.add_template_attribute(
                "_attr_native_dew_point",
                self._dew_point_template,
                on_update=self._update_dew_point,
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
        if self._humidity_template:
            self.add_template_attribute(
                "_attr_humidity",
                self._humidity_template,
                on_update=self._update_humidity,
            )
        if self._ozone_template:
            self.add_template_attribute(
                "_attr_ozone",
                self._ozone_template,
                on_update=self._update_ozone,
            )
        if self._pressure_template:
            self.add_template_attribute(
                "_attr_native_pressure",
                self._pressure_template,
                on_update=self._update_pressure,
            )
        if self._temperature_template:
            self.add_template_attribute(
                "_attr_native_temperature",
                self._temperature_template,
                on_update=self._update_temperature,
            )
        if self._uv_index_template:
            self.add_template_attribute(
                "_attr_uv_index",
                self._uv_index_template,
                on_update=self._update_uv_index,
            )
        if self._visibility_template:
            self.add_template_attribute(
                "_attr_native_visibility",
                self._visibility_template,
                on_update=self._update_visibility,
            )
        if self._wind_bearing_template:
            self.add_template_attribute(
                "_attr_wind_bearing",
                self._wind_bearing_template,
                on_update=self._update_wind_bearing,
            )
        if self._wind_gust_speed_template:
            self.add_template_attribute(
                "_attr_native_wind_gust_speed",
                self._wind_gust_speed_template,
                on_update=self._update_wind_gust_speed,
            )
        if self._wind_speed_template:
            self.add_template_attribute(
                "_attr_native_wind_speed",
                self._wind_speed_template,
                on_update=self._update_wind_speed,
            )

        super()._async_setup_templates()

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_daily or []

    async def async_forecast_hourly(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_hourly or []

    async def async_forecast_twice_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_twice_daily or []

    @callback
    def _update_forecast(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
        result: list[Forecast] | TemplateError,
    ) -> None:
        """Save template result and trigger forecast listener."""
        attr_result = None if isinstance(result, TemplateError) else result
        setattr(self, f"_forecast_{forecast_type}", attr_result)
        self.hass.async_create_task(
            self.async_update_listeners([forecast_type]), eager_start=True
        )


@dataclass(kw_only=True)
class WeatherExtraStoredData(ExtraStoredData):
    """Object to hold extra stored data."""

    last_apparent_temperature: float | None
    last_cloud_coverage: int | None
    last_dew_point: float | None
    last_humidity: float | None
    last_ozone: float | None
    last_pressure: float | None
    last_temperature: float | None
    last_uv_index: float | None
    last_visibility: float | None
    last_wind_bearing: float | str | None
    last_wind_gust_speed: float | None
    last_wind_speed: float | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of the event data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, restored: dict[str, Any]) -> Self | None:
        """Initialize a stored event state from a dict."""
        try:
            return cls(
                last_apparent_temperature=restored["last_apparent_temperature"],
                last_cloud_coverage=restored["last_cloud_coverage"],
                last_dew_point=restored["last_dew_point"],
                last_humidity=restored["last_humidity"],
                last_ozone=restored["last_ozone"],
                last_pressure=restored["last_pressure"],
                last_temperature=restored["last_temperature"],
                last_uv_index=restored["last_uv_index"],
                last_visibility=restored["last_visibility"],
                last_wind_bearing=restored["last_wind_bearing"],
                last_wind_gust_speed=restored["last_wind_gust_speed"],
                last_wind_speed=restored["last_wind_speed"],
            )
        except KeyError:
            return None


class TriggerWeatherEntity(TriggerEntity, AbstractTemplateWeather, RestoreEntity):
    """Weather entity based on trigger data."""

    domain = WEATHER_DOMAIN
    extra_template_keys = (
        CONF_CONDITION,
        CONF_TEMPERATURE,
        CONF_HUMIDITY,
    )

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateWeather.__init__(self, config, None)

        for key in (
            CONF_APPARENT_TEMPERATURE,
            CONF_CLOUD_COVERAGE,
            CONF_DEW_POINT,
            CONF_FORECAST_DAILY,
            CONF_FORECAST_HOURLY,
            CONF_FORECAST_TWICE_DAILY,
            CONF_OZONE,
            CONF_PRESSURE,
            CONF_UV_INDEX,
            CONF_VISIBILITY,
            CONF_WIND_BEARING,
            CONF_WIND_GUST_SPEED,
            CONF_WIND_SPEED,
        ):
            if isinstance(config.get(key), template.Template):
                self._to_render_simple.append(key)
                self._parse_result.add(key)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            (state := await self.async_get_last_state())
            and state.state is not None
            and state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and (weather_data := await self.async_get_last_weather_data())
        ):
            self._attr_native_apparent_temperature = (
                weather_data.last_apparent_temperature
            )
            self._attr_cloud_coverage = weather_data.last_cloud_coverage
            self._attr_condition = state.state
            self._attr_native_dew_point = weather_data.last_dew_point
            self._attr_humidity = weather_data.last_humidity
            self._attr_ozone = weather_data.last_ozone
            self._attr_native_pressure = weather_data.last_pressure
            self._attr_native_temperature = weather_data.last_temperature
            self._attr_uv_index = weather_data.last_uv_index
            self._attr_native_visibility = weather_data.last_visibility
            self._attr_wind_bearing = weather_data.last_wind_bearing
            self._attr_native_wind_gust_speed = weather_data.last_wind_gust_speed
            self._attr_native_wind_speed = weather_data.last_wind_speed

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update of the data."""
        self._process_data()

        if not self.available:
            self.async_write_ha_state()
            return

        write_ha_state = False
        for key, updater in (
            (CONF_APPARENT_TEMPERATURE, self._update_apparent_temperature),
            (CONF_CLOUD_COVERAGE, self._update_coverage),
            (CONF_CONDITION, self._update_condition),
            (CONF_DEW_POINT, self._update_dew_point),
            (CONF_HUMIDITY, self._update_humidity),
            (CONF_OZONE, self._update_ozone),
            (CONF_PRESSURE, self._update_pressure),
            (CONF_TEMPERATURE, self._update_temperature),
            (CONF_UV_INDEX, self._update_uv_index),
            (CONF_VISIBILITY, self._update_visibility),
            (CONF_WIND_BEARING, self._update_wind_bearing),
            (CONF_WIND_GUST_SPEED, self._update_wind_gust_speed),
            (CONF_WIND_SPEED, self._update_wind_speed),
        ):
            if (rendered := self._rendered.get(key)) is not None:
                updater(rendered)
                write_ha_state = True

        if write_ha_state:
            self.async_write_ha_state()

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return (
            self._validate_forecast("daily", self._rendered.get(CONF_FORECAST_DAILY))
            or []
        )

    async def async_forecast_hourly(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return (
            self._validate_forecast("hourly", self._rendered.get(CONF_FORECAST_HOURLY))
            or []
        )

    async def async_forecast_twice_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return (
            self._validate_forecast(
                "twice_daily", self._rendered.get(CONF_FORECAST_TWICE_DAILY)
            )
            or []
        )

    @property
    def extra_restore_state_data(self) -> WeatherExtraStoredData:
        """Return weather specific state data to be restored."""
        return WeatherExtraStoredData(
            last_apparent_temperature=self._rendered.get(CONF_APPARENT_TEMPERATURE),
            last_cloud_coverage=self._rendered.get(CONF_CLOUD_COVERAGE),
            last_dew_point=self._rendered.get(CONF_DEW_POINT),
            last_humidity=self._rendered.get(CONF_HUMIDITY),
            last_ozone=self._rendered.get(CONF_OZONE),
            last_pressure=self._rendered.get(CONF_PRESSURE),
            last_temperature=self._rendered.get(CONF_TEMPERATURE),
            last_uv_index=self._rendered.get(CONF_UV_INDEX),
            last_visibility=self._rendered.get(CONF_VISIBILITY),
            last_wind_bearing=self._rendered.get(CONF_WIND_BEARING),
            last_wind_gust_speed=self._rendered.get(CONF_WIND_GUST_SPEED),
            last_wind_speed=self._rendered.get(CONF_WIND_SPEED),
        )

    async def async_get_last_weather_data(self) -> WeatherExtraStoredData | None:
        """Restore weather specific state data."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return WeatherExtraStoredData.from_dict(restored_last_extra_data.as_dict())
