"""The tests for Weather platforms."""

from typing import Any

from homeassistant.components.weather import (
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_HUMIDITY,
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
    DOMAIN,
    Forecast,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_integration,
    mock_platform,
)
from tests.testing_config.custom_components.test import weather as WeatherPlatform


class MockWeatherTest(WeatherPlatform.MockWeather):
    """Mock weather class."""

    def __init__(self, **values: Any) -> None:
        """Initialize."""
        super().__init__(**values)
        self.forecast_list: list[Forecast] | None = [
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
                ATTR_FORECAST_NATIVE_PRECIPITATION: self._values.get(
                    "native_precipitation"
                ),
                ATTR_FORECAST_HUMIDITY: self.humidity,
            }
        ]


async def create_entity(
    hass: HomeAssistant,
    mock_weather: type[WeatherPlatform.MockWeather],
    manifest_extra: dict[str, Any] | None,
    **kwargs,
) -> WeatherPlatform.MockWeather:
    """Create the weather entity to run tests on."""
    kwargs = {
        "native_temperature": None,
        "native_temperature_unit": None,
        "is_daytime": True,
        **kwargs,
    }

    weather_entity = mock_weather(
        name="Testing",
        entity_id="weather.testing",
        condition=ATTR_CONDITION_SUNNY,
        **kwargs,
    )

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    async def async_setup_entry_weather_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test weather platform via config entry."""
        async_add_entities([weather_entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=async_setup_entry_init,
            partial_manifest=manifest_extra,
        ),
        built_in=False,
    )
    mock_platform(
        hass,
        "test.weather",
        MockPlatform(async_setup_entry=async_setup_entry_weather_platform),
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return weather_entity
