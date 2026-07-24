"""Support for KNX weather entities."""

from typing import override

from xknx.devices import Weather as XknxWeather

from homeassistant import config_entries
from homeassistant.components.weather import WeatherEntity
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    Platform,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SYNC_STATE, DOMAIN, KNX_MODULE_KEY
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .knx_module import KNXModule
from .schema import WeatherSchema
from .storage.const import (
    CONF_ENTITY,
    CONF_GA_AIR_PRESSURE,
    CONF_GA_BRIGHTNESS_EAST,
    CONF_GA_BRIGHTNESS_NORTH,
    CONF_GA_BRIGHTNESS_SOUTH,
    CONF_GA_BRIGHTNESS_WEST,
    CONF_GA_DAY_NIGHT,
    CONF_GA_FROST_ALARM,
    CONF_GA_HUMIDITY,
    CONF_GA_RAIN_ALARM,
    CONF_GA_TEMPERATURE,
    CONF_GA_WIND_ALARM,
    CONF_GA_WIND_BEARING,
    CONF_GA_WIND_SPEED,
    CONF_INVERT_DAY_NIGHT,
)
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up weather entities for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.WEATHER,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiWeather,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.WEATHER):
        entities.extend(
            KnxYamlWeather(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.WEATHER):
        entities.extend(
            KnxUiWeather(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxWeather(WeatherEntity):
    """Representation of a KNX weather device."""

    _device: XknxWeather
    _attr_native_pressure_unit = UnitOfPressure.PA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return current temperature in C."""
        return self._device.temperature

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return current air pressure in Pa."""
        return self._device.air_pressure

    @property
    @override
    def condition(self) -> str:
        """Return current weather condition."""
        return self._device.ha_current_state().value

    @property
    @override
    def humidity(self) -> float | None:
        """Return current humidity."""
        return self._device.humidity

    @property
    @override
    def wind_bearing(self) -> int | None:
        """Return current wind bearing in degrees."""
        return self._device.wind_bearing

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return current wind speed in m/s."""
        return self._device.wind_speed


class KnxYamlWeather(_KnxWeather, KnxYamlEntity):
    """Representation of a KNX weather device configured from YAML."""

    _device: XknxWeather

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize of a KNX weather device."""
        self._device = XknxWeather(
            knx_module.xknx,
            name=config[CONF_NAME],
            sync_state=config[WeatherSchema.CONF_SYNC_STATE],
            group_address_temperature=config[
                WeatherSchema.CONF_KNX_TEMPERATURE_ADDRESS
            ],
            group_address_brightness_south=config.get(
                WeatherSchema.CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS
            ),
            group_address_brightness_east=config.get(
                WeatherSchema.CONF_KNX_BRIGHTNESS_EAST_ADDRESS
            ),
            group_address_brightness_west=config.get(
                WeatherSchema.CONF_KNX_BRIGHTNESS_WEST_ADDRESS
            ),
            group_address_brightness_north=config.get(
                WeatherSchema.CONF_KNX_BRIGHTNESS_NORTH_ADDRESS
            ),
            group_address_wind_speed=config.get(
                WeatherSchema.CONF_KNX_WIND_SPEED_ADDRESS
            ),
            group_address_wind_bearing=config.get(
                WeatherSchema.CONF_KNX_WIND_BEARING_ADDRESS
            ),
            group_address_rain_alarm=config.get(
                WeatherSchema.CONF_KNX_RAIN_ALARM_ADDRESS
            ),
            group_address_frost_alarm=config.get(
                WeatherSchema.CONF_KNX_FROST_ALARM_ADDRESS
            ),
            group_address_wind_alarm=config.get(
                WeatherSchema.CONF_KNX_WIND_ALARM_ADDRESS
            ),
            group_address_day_night=config.get(
                WeatherSchema.CONF_KNX_DAY_NIGHT_ADDRESS
            ),
            group_address_air_pressure=config.get(
                WeatherSchema.CONF_KNX_AIR_PRESSURE_ADDRESS
            ),
            group_address_humidity=config.get(WeatherSchema.CONF_KNX_HUMIDITY_ADDRESS),
        )
        super().__init__(
            knx_module=knx_module,
            unique_id=str(self._device._temperature.group_address_state),  # noqa: SLF001
            name=config[CONF_NAME],
            entity_category=config.get(CONF_ENTITY_CATEGORY),
        )


class KnxUiWeather(_KnxWeather, KnxUiEntity):
    """Representation of a KNX weather device configured from UI."""

    _device: XknxWeather

    def __init__(
        self, knx_module: KNXModule, unique_id: str, config: ConfigType
    ) -> None:
        """Initialize of a KNX weather device."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        self._device = XknxWeather(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            sync_state=knx_conf.get(CONF_SYNC_STATE),
            group_address_temperature=knx_conf.get_state_and_passive(
                CONF_GA_TEMPERATURE
            ),
            group_address_brightness_south=knx_conf.get_state_and_passive(
                CONF_GA_BRIGHTNESS_SOUTH
            ),
            group_address_brightness_east=knx_conf.get_state_and_passive(
                CONF_GA_BRIGHTNESS_EAST
            ),
            group_address_brightness_west=knx_conf.get_state_and_passive(
                CONF_GA_BRIGHTNESS_WEST
            ),
            group_address_brightness_north=knx_conf.get_state_and_passive(
                CONF_GA_BRIGHTNESS_NORTH
            ),
            group_address_wind_speed=knx_conf.get_state_and_passive(CONF_GA_WIND_SPEED),
            group_address_wind_bearing=knx_conf.get_state_and_passive(
                CONF_GA_WIND_BEARING
            ),
            group_address_rain_alarm=knx_conf.get_state_and_passive(CONF_GA_RAIN_ALARM),
            group_address_frost_alarm=knx_conf.get_state_and_passive(
                CONF_GA_FROST_ALARM
            ),
            group_address_wind_alarm=knx_conf.get_state_and_passive(CONF_GA_WIND_ALARM),
            group_address_day_night=knx_conf.get_state_and_passive(CONF_GA_DAY_NIGHT),
            group_address_air_pressure=knx_conf.get_state_and_passive(
                CONF_GA_AIR_PRESSURE
            ),
            group_address_humidity=knx_conf.get_state_and_passive(CONF_GA_HUMIDITY),
            # xknx treats a raw `1` as day, so its default is inverted compared to
            # DPT 1.024 (0 = day, 1 = night) which the UI flag represents.
            invert_day_night=not knx_conf.get(CONF_INVERT_DAY_NIGHT),
        )
