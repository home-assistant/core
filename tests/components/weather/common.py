"""Provide common tests tools for Weather."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_DEW_POINT,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
    DOMAIN as WEATHER_DOMAIN,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PRECISION_HALVES,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


class MockWeatherEntity(WeatherEntity):
    """Mock a Weather Entity."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_humidity = 50
        self._attr_ozone = 20
        self._attr_cloud_coverage = 20
        self._attr_uv_index = 1.2
        self._attr_precision = PRECISION_HALVES
        self._attr_wind_bearing = 180
        self._attr_native_precipitation_unit = UnitOfLength.MILLIMETERS
        self._attr_native_pressure = 10
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_native_temperature = 20
        self._attr_native_apparent_temperature = 25
        self._attr_native_dew_point = 2
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_visibility = 30
        self._attr_native_visibility_unit = UnitOfLength.KILOMETERS
        self._attr_native_wind_gust_speed = 10
        self._attr_native_wind_speed = 3
        self._attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
        self._attr_forecast = [
            Forecast(
                datetime=datetime(2022, 6, 20, 00, 00, 00, tzinfo=dt_util.UTC),
                native_precipitation=1,
                native_temperature=20,
                native_dew_point=2,
            )
        ]
        self.native_precipitation = 20

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the forecast_daily."""
        return self._attr_forecast

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the forecast_twice_daily."""
        return [
            {
                ATTR_FORECAST_NATIVE_TEMP: self.native_temperature,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: self.native_apparent_temperature,
                ATTR_FORECAST_NATIVE_TEMP_LOW: self.native_temperature,
                ATTR_FORECAST_NATIVE_DEW_POINT: self.native_dew_point,
                ATTR_FORECAST_CLOUD_COVERAGE: self.cloud_coverage,
                ATTR_FORECAST_NATIVE_PRESSURE: self.native_pressure,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self.native_wind_gust_speed,
                ATTR_FORECAST_NATIVE_WIND_SPEED: self.native_wind_speed,
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing,
                ATTR_FORECAST_UV_INDEX: self.uv_index,
                ATTR_FORECAST_NATIVE_PRECIPITATION: self.native_precipitation,
                ATTR_FORECAST_HUMIDITY: self.humidity,
                ATTR_FORECAST_IS_DAYTIME: True,
            }
        ]

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the forecast_hourly."""
        return [
            {
                ATTR_FORECAST_NATIVE_TEMP: self.native_temperature,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: self.native_apparent_temperature,
                ATTR_FORECAST_NATIVE_TEMP_LOW: self.native_temperature,
                ATTR_FORECAST_NATIVE_DEW_POINT: self.native_dew_point,
                ATTR_FORECAST_CLOUD_COVERAGE: self.cloud_coverage,
                ATTR_FORECAST_NATIVE_PRESSURE: self.native_pressure,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: self.native_wind_gust_speed,
                ATTR_FORECAST_NATIVE_WIND_SPEED: self.native_wind_speed,
                ATTR_FORECAST_WIND_BEARING: self.wind_bearing,
                ATTR_FORECAST_UV_INDEX: self.uv_index,
                ATTR_FORECAST_NATIVE_PRECIPITATION: self.native_precipitation,
                ATTR_FORECAST_HUMIDITY: self.humidity,
            }
        ]


class MockWeatherEntityPrecision(WeatherEntity):
    """Mock a Weather Entity with precision."""

    def __init__(self) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_condition = ATTR_CONDITION_SUNNY
        self._attr_native_temperature = 20.3
        self._attr_native_apparent_temperature = 25.3
        self._attr_native_dew_point = 2.3
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_precision = PRECISION_HALVES


class MockWeatherTestEntity(MockWeatherEntity):
    """Mock a Weather Entity."""

    def __init__(self, values: dict[str, Any] | None = None) -> None:
        """Initiate Entity."""
        super().__init__()
        self._attr_name = "test"
        if values:
            for key, value in values.items():
                setattr(self, values[key], values[value])


async def mock_setup(
    hass: HomeAssistant,
    weather_entity: MockWeatherTestEntity,
) -> None:
    """Set up a test provider."""
    mock_integration(hass, MockModule(domain=TEST_DOMAIN))

    async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigType,
        async_add_entities: AddEntitiesCallback,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> None:
        """Set up test tts platform via config entry."""
        async_add_entities([weather_entity])

    loaded_platform = MockPlatform(async_setup_platform=async_setup_platform)
    mock_platform(hass, f"{TEST_DOMAIN}.{WEATHER_DOMAIN}", loaded_platform)

    await async_setup_component(
        hass, WEATHER_DOMAIN, {WEATHER_DOMAIN: {"platform": TEST_DOMAIN}}
    )
    await hass.async_block_till_done()


async def mock_config_entry_setup(
    hass: HomeAssistant, weather_entity: MockWeatherTestEntity
) -> MockConfigEntry:
    """Set up a test tts platform via config entry."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setup(
            config_entry, WEATHER_DOMAIN
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload test config entry."""
        await hass.config_entries.async_forward_entry_unload(
            config_entry, WEATHER_DOMAIN
        )
        return True

    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test tts platform via config entry."""
        async_add_entities([weather_entity])

    loaded_platform = MockPlatform(async_setup_entry=async_setup_entry_platform)
    mock_platform(hass, f"{TEST_DOMAIN}.{WEATHER_DOMAIN}", loaded_platform)

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry
