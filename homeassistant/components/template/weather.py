"""Template platform that aggregates meteorological data."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
import logging
from typing import Any, Literal, Self

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
from homeassistant.helpers import config_validation as cv
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

from . import TriggerUpdateCoordinator, validators as template_validators
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

_LOGGER = logging.getLogger(__name__)

CHECK_FORECAST_KEYS = (
    set()
    .union(Forecast.__annotations__.keys())
    # Manually add the forecast resulting attributes that only exists
    #  as native_* in the Forecast definition
    .union(("apparent_temperature", "wind_gust_speed", "dew_point"))
)

CONDITION_CLASSES = [
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_CONDITION_WINDY,
]

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

# These options that are templates all have _template. These fields will
# enter deprecation after legacy templates are removed.
WEATHER_COMMON_LEGACY_SCHEMA = vol.Schema(
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

WEATHER_COMMON_MODERN_SCHEMA = vol.Schema(
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
)


WEATHER_YAML_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_UV_INDEX_TEMPLATE): cv.template,
        }
    )
    .extend(WEATHER_COMMON_LEGACY_SCHEMA.schema)
    .extend(
        make_template_entity_common_modern_schema(WEATHER_DOMAIN, DEFAULT_NAME).schema
    )
)

WEATHER_MODERN_YAML_SCHEMA = WEATHER_COMMON_MODERN_SCHEMA.extend(
    make_template_entity_common_modern_schema(WEATHER_DOMAIN, DEFAULT_NAME).schema
)

PLATFORM_SCHEMA = (
    vol.Schema(
        {
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.template,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(WEATHER_COMMON_LEGACY_SCHEMA.schema)
    .extend(WEATHER_PLATFORM_SCHEMA.schema)
)


WEATHER_CONFIG_ENTRY_SCHEMA = WEATHER_COMMON_MODERN_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)


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


def validate_forecast(
    entity: AbstractTemplateWeather,
    option: str,
    forecast_type: Literal["daily", "hourly", "twice_daily"],
) -> Callable[[Any], list[Forecast] | None]:
    """Validate a forecast."""

    weather_message = (
        "see Weather documentation https://www.home-assistant.io/integrations/weather/"
    )

    def validate(result: Any) -> list[Forecast] | None:
        if template_validators.check_result_for_none(result):
            return None

        if not isinstance(result, list):
            template_validators.log_validation_result_error(
                entity,
                option,
                result,
                f"expected a list, {weather_message}",
            )

        raised = False
        for forecast in result:
            if not isinstance(forecast, dict):
                raised = True
                template_validators.log_validation_result_error(
                    entity,
                    option,
                    result,
                    f"expected a list of forecast dictionaries, got {forecast}, {weather_message}",
                )
                continue

            diff_result = set().union(forecast.keys()).difference(CHECK_FORECAST_KEYS)
            if diff_result:
                raised = True
                template_validators.log_validation_result_error(
                    entity,
                    option,
                    result,
                    f"expected valid forecast keys, unallowed keys: ({diff_result}) for {forecast}, {weather_message}",
                )
            if forecast_type == "twice_daily" and "is_daytime" not in forecast:
                raised = True
                template_validators.log_validation_result_error(
                    entity,
                    option,
                    result,
                    f"`is_daytime` is missing in twice_daily forecast {forecast}, {weather_message}",
                )
            if "datetime" not in forecast:
                raised = True
                template_validators.log_validation_result_error(
                    entity,
                    option,
                    result,
                    f"`datetime` is missing in forecast, got {forecast}, {weather_message}",
                )

        if raised:
            return None

        return result

    return validate


class AbstractTemplateWeather(AbstractTemplateEntity, WeatherEntity):
    """Representation of a template weathers features."""

    _entity_id_format = ENTITY_ID_FORMAT
    _optimistic_entity = True

    # The super init is not called because TemplateEntity and TriggerEntity will call AbstractTemplateEntity.__init__.
    # This ensures that the __init__ on AbstractTemplateEntity is not called twice.
    def __init__(  # pylint: disable=super-init-not-called
        self, config: dict[str, Any]
    ) -> None:
        """Initialize the features."""

        # Required options
        self.setup_template(
            CONF_CONDITION,
            "_attr_condition",
            template_validators.item_in_list(self, CONF_CONDITION, CONDITION_CLASSES),
        )
        self.setup_template(
            CONF_HUMIDITY,
            "_attr_humidity",
            template_validators.number(self, CONF_HUMIDITY, 0.0, 100.0),
        )
        self.setup_template(
            CONF_TEMPERATURE,
            "_attr_native_temperature",
            template_validators.number(self, CONF_TEMPERATURE),
        )

        # Optional options

        self.setup_template(
            CONF_ATTRIBUTION,
            "_attribution",
            vol.Coerce(str),
        )
        self.setup_template(
            CONF_WIND_BEARING, "_attr_wind_bearing", None, self._update_wind_bearing
        )

        # Optional numeric options
        for option, attribute in (
            (CONF_APPARENT_TEMPERATURE, "_attr_native_apparent_temperature"),
            (CONF_CLOUD_COVERAGE, "_attr_cloud_coverage"),
            (CONF_DEW_POINT, "_attr_native_dew_point"),
            (CONF_OZONE, "_attr_ozone"),
            (CONF_PRESSURE, "_attr_native_pressure"),
            (CONF_UV_INDEX, "_attr_uv_index"),
            (CONF_VISIBILITY, "_attr_native_visibility"),
            (CONF_WIND_GUST_SPEED, "_attr_native_wind_gust_speed"),
            (CONF_WIND_SPEED, "_attr_native_wind_speed"),
        ):
            self.setup_template(
                option, attribute, template_validators.number(self, option)
            )

        # Forecasts

        self._forecast_daily: list[Forecast] | None = []
        self.setup_template(
            CONF_FORECAST_DAILY,
            "_forecast_daily",
            validate_forecast(self, CONF_FORECAST_DAILY, "daily"),
            self._update_forecast("daily"),
        )

        self._forecast_hourly: list[Forecast] | None = []
        self.setup_template(
            CONF_FORECAST_HOURLY,
            "_forecast_hourly",
            validate_forecast(self, CONF_FORECAST_HOURLY, "hourly"),
            self._update_forecast("hourly"),
        )

        self._forecast_twice_daily: list[Forecast] | None = []
        self.setup_template(
            CONF_FORECAST_TWICE_DAILY,
            "_forecast_twice_daily",
            validate_forecast(self, CONF_FORECAST_TWICE_DAILY, "twice_daily"),
            self._update_forecast("twice_daily"),
        )

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
        if CONF_FORECAST_DAILY in self._templates:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_DAILY
        if CONF_FORECAST_HOURLY in self._templates:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_HOURLY
        if CONF_FORECAST_TWICE_DAILY in self._templates:
            self._attr_supported_features |= WeatherEntityFeature.FORECAST_TWICE_DAILY

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        if self._attribution is None:
            return "Powered by Home Assistant"
        return self._attribution

    @callback
    def _update_wind_bearing(self, result: Any) -> None:
        try:
            self._attr_wind_bearing = vol.Coerce(float)(result)
        except vol.Invalid:
            self._attr_wind_bearing = vol.Coerce(str)(result)

    @callback
    def _update_forecast(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
    ) -> Callable[[list[Forecast] | None], None]:
        """Save template result and trigger forecast listener."""

        def update(result: list[Forecast] | None) -> None:
            setattr(self, f"_forecast_{forecast_type}", result)
            self.hass.async_create_task(
                self.async_update_listeners([forecast_type]), eager_start=True
            )

        return update

    async def async_forecast_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_daily or []

    async def async_forecast_hourly(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_hourly or []

    async def async_forecast_twice_daily(self) -> list[Forecast]:
        """Return the daily forecast in native units."""
        return self._forecast_twice_daily or []


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
        for key, vtypes in (
            ("last_apparent_temperature", (float, int)),
            ("last_cloud_coverage", (float, int)),
            ("last_dew_point", (float, int)),
            ("last_humidity", (float, int)),
            ("last_ozone", (float, int)),
            ("last_pressure", (float, int)),
            ("last_temperature", (float, int)),
            ("last_uv_index", (float, int)),
            ("last_visibility", (float, int)),
            ("last_wind_bearing", (float, int, str)),
            ("last_wind_gust_speed", (float, int)),
            ("last_wind_speed", (float, int)),
        ):
            # This is needed to safeguard against previous restore data that has strings
            # instead of floats or ints.
            if key not in restored or (
                (value := restored[key]) is not None and not isinstance(value, vtypes)
            ):
                return None

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


class TriggerWeatherEntity(TriggerEntity, AbstractTemplateWeather, RestoreEntity):
    """Weather entity based on trigger data."""

    domain = WEATHER_DOMAIN

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize."""
        TriggerEntity.__init__(self, hass, coordinator, config)
        AbstractTemplateWeather.__init__(self, config)

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

    @property
    def extra_restore_state_data(self) -> WeatherExtraStoredData:
        """Return weather specific state data to be restored."""
        return WeatherExtraStoredData(
            last_apparent_temperature=self.native_apparent_temperature,
            last_cloud_coverage=self._attr_cloud_coverage,
            last_dew_point=self.native_dew_point,
            last_humidity=self.humidity,
            last_ozone=self.ozone,
            last_pressure=self.native_pressure,
            last_temperature=self.native_temperature,
            last_uv_index=self.uv_index,
            last_visibility=self.native_visibility,
            last_wind_bearing=self.wind_bearing,
            last_wind_gust_speed=self.native_wind_gust_speed,
            last_wind_speed=self.native_wind_speed,
        )

    async def async_get_last_weather_data(self) -> WeatherExtraStoredData | None:
        """Restore weather specific state data."""
        if (restored_last_extra_data := await self.async_get_last_extra_data()) is None:
            return None
        return WeatherExtraStoredData.from_dict(restored_last_extra_data.as_dict())
