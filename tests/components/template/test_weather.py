"""The tests for the Template Weather platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import template
from homeassistant.components.template.const import CONF_PICTURE
from homeassistant.components.weather import (
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_UV_INDEX,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
    Forecast,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_PICTURE,
    ATTR_ICON,
    CONF_ICON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    async_get_flow_preview_state,
    async_trigger,
    make_test_trigger,
    setup_entity,
)

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache_with_extra_data,
)
from tests.typing import WebSocketGenerator

ATTR_FORECAST = "forecast"

TEST_STATE_ENTITY_ID = "weather.test_state"
TEST_SENSORS = (
    "sensor.apparent_temperature",
    "sensor.attribution",
    "sensor.cloud_coverage",
    "sensor.condition",
    "sensor.dew_point",
    "sensor.forecast",
    "sensor.forecast_daily",
    "sensor.forecast_hourly",
    "sensor.forecast_twice_daily",
    "sensor.humidity",
    "sensor.ozone",
    "sensor.pressure",
    "sensor.temperature",
    "sensor.uv_index",
    "sensor.visibility",
    "sensor.wind_bearing",
    "sensor.wind_gust_speed",
    "sensor.wind_speed",
)
TEST_WEATHER = TemplatePlatformSetup(
    WEATHER_DOMAIN,
    None,
    "template_weather",
    make_test_trigger(TEST_STATE_ENTITY_ID, *TEST_SENSORS),
)

TEST_LEGACY_REQUIRED = {
    "condition_template": "sunny",
    "temperature_template": "{{ 20 }}",
    "humidity_template": "{{ 25 }}",
}

TEST_MODERN_REQUIRED = {
    "condition": "sunny",
    "temperature": "{{ 20 }}",
    "humidity": "{{ 25 }}",
}


@pytest.fixture
async def setup_weather(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of number integration."""
    await setup_entity(hass, TEST_WEATHER, style, 1, config)


@pytest.mark.parametrize(
    ("style", "config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "apparent_temperature_template": "{{ states('sensor.apparent_temperature') }}",
                "attribution_template": "{{ states('sensor.attribution') }}",
                "cloud_coverage_template": "{{ states('sensor.cloud_coverage') }}",
                "condition_template": "{{ states('sensor.condition') }}",
                "dew_point_template": "{{ states('sensor.dew_point') }}",
                "humidity_template": "{{ states('sensor.humidity') | int }}",
                "ozone_template": "{{ states('sensor.ozone') }}",
                "pressure_template": "{{ states('sensor.pressure') }}",
                "temperature_template": "{{ states('sensor.temperature') | float }}",
                "unique_id": "abc123",
                "visibility_template": "{{ states('sensor.visibility') }}",
                "wind_bearing_template": "{{ states('sensor.wind_bearing') }}",
                "wind_gust_speed_template": "{{ states('sensor.wind_gust_speed') }}",
                "wind_speed_template": "{{ states('sensor.wind_speed') }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "apparent_temperature_template": "{{ states('sensor.apparent_temperature') }}",
                "attribution_template": "{{ states('sensor.attribution') }}",
                "cloud_coverage_template": "{{ states('sensor.cloud_coverage') }}",
                "condition_template": "{{ states('sensor.condition') }}",
                "dew_point_template": "{{ states('sensor.dew_point') }}",
                "humidity_template": "{{ states('sensor.humidity') | int }}",
                "ozone_template": "{{ states('sensor.ozone') }}",
                "pressure_template": "{{ states('sensor.pressure') }}",
                "temperature_template": "{{ states('sensor.temperature') | float }}",
                "unique_id": "abc123",
                "uv_index_template": "{{ states('sensor.uv_index') }}",
                "visibility_template": "{{ states('sensor.visibility') }}",
                "wind_bearing_template": "{{ states('sensor.wind_bearing') }}",
                "wind_gust_speed_template": "{{ states('sensor.wind_gust_speed') }}",
                "wind_speed_template": "{{ states('sensor.wind_speed') }}",
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "apparent_temperature_template": "{{ states('sensor.apparent_temperature') }}",
                "attribution_template": "{{ states('sensor.attribution') }}",
                "cloud_coverage_template": "{{ states('sensor.cloud_coverage') }}",
                "condition_template": "{{ states('sensor.condition') }}",
                "dew_point_template": "{{ states('sensor.dew_point') }}",
                "humidity_template": "{{ states('sensor.humidity') | int }}",
                "ozone_template": "{{ states('sensor.ozone') }}",
                "pressure_template": "{{ states('sensor.pressure') }}",
                "temperature_template": "{{ states('sensor.temperature') | float }}",
                "unique_id": "abc123",
                "uv_index_template": "{{ states('sensor.uv_index') }}",
                "visibility_template": "{{ states('sensor.visibility') }}",
                "wind_bearing_template": "{{ states('sensor.wind_bearing') }}",
                "wind_gust_speed_template": "{{ states('sensor.wind_gust_speed') }}",
                "wind_speed_template": "{{ states('sensor.wind_speed') }}",
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "apparent_temperature": "{{ states('sensor.apparent_temperature') }}",
                "attribution": "{{ states('sensor.attribution') }}",
                "cloud_coverage": "{{ states('sensor.cloud_coverage') }}",
                "condition": "{{ states('sensor.condition') }}",
                "dew_point": "{{ states('sensor.dew_point') }}",
                "humidity": "{{ states('sensor.humidity') | int }}",
                "ozone": "{{ states('sensor.ozone') }}",
                "pressure": "{{ states('sensor.pressure') }}",
                "temperature": "{{ states('sensor.temperature') | float }}",
                "unique_id": "abc123",
                "uv_index": "{{ states('sensor.uv_index') }}",
                "visibility": "{{ states('sensor.visibility') }}",
                "wind_bearing": "{{ states('sensor.wind_bearing') }}",
                "wind_gust_speed": "{{ states('sensor.wind_gust_speed') }}",
                "wind_speed": "{{ states('sensor.wind_speed') }}",
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "apparent_temperature": "{{ states('sensor.apparent_temperature') }}",
                "attribution": "{{ states('sensor.attribution') }}",
                "cloud_coverage": "{{ states('sensor.cloud_coverage') }}",
                "condition": "{{ states('sensor.condition') }}",
                "dew_point": "{{ states('sensor.dew_point') }}",
                "humidity": "{{ states('sensor.humidity') }}",
                "ozone": "{{ states('sensor.ozone') }}",
                "pressure": "{{ states('sensor.pressure') }}",
                "temperature": "{{ states('sensor.temperature') }}",
                "unique_id": "abc123",
                "uv_index": "{{ states('sensor.uv_index') }}",
                "visibility": "{{ states('sensor.visibility') }}",
                "wind_bearing": "{{ states('sensor.wind_bearing') }}",
                "wind_gust_speed": "{{ states('sensor.wind_gust_speed') }}",
                "wind_speed": "{{ states('sensor.wind_speed') }}",
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_weather")
async def test_template_state_text(
    hass: HomeAssistant, style: ConfigurationStyle
) -> None:
    """Test the state text of a template."""
    await async_trigger(hass, "sensor.condition", "sunny")
    for entity_id, v_attr, value in (
        ("sensor.apparent_temperature", ATTR_WEATHER_APPARENT_TEMPERATURE, 25),
        ("sensor.attribution", ATTR_ATTRIBUTION, "Custom"),
        ("sensor.cloud_coverage", ATTR_WEATHER_CLOUD_COVERAGE, 75),
        ("sensor.dew_point", ATTR_WEATHER_DEW_POINT, 2.2),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
        ("sensor.ozone", ATTR_WEATHER_OZONE, 25),
        ("sensor.pressure", ATTR_WEATHER_PRESSURE, 1000),
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.uv_index", ATTR_WEATHER_UV_INDEX, 3.7),
        ("sensor.visibility", ATTR_WEATHER_VISIBILITY, 4.6),
        ("sensor.wind_bearing", ATTR_WEATHER_WIND_BEARING, 180),
        ("sensor.wind_gust_speed", ATTR_WEATHER_WIND_GUST_SPEED, 30),
        ("sensor.wind_speed", ATTR_WEATHER_WIND_SPEED, 20),
    ):
        await async_trigger(hass, entity_id, str(value))
        state = hass.states.get(TEST_WEATHER.entity_id)
        assert state is not None
        assert state.state == "sunny"
        # Legacy template entities do not support uv_index, modern and trigger do.
        assert state.attributes.get(v_attr) == value or (
            entity_id == "sensor.uv_index" and style == ConfigurationStyle.LEGACY
        )


@pytest.mark.parametrize(
    ("style", "config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "forecast_daily": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_hourly": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_twice_daily": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_MODERN_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "forecast_daily": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_hourly": "{{ state_attr('sensor.forecast', 'forecast') }}",
                "forecast_twice_daily": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_MODERN_REQUIRED,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_weather")
async def test_forecasts(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test forecast service."""
    hass.states.async_set(
        "sensor.forecast",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                )
            ]
        },
    )
    hass.states.async_set(
        "sensor.forecast_twice_daily",
        "fog",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="fog",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                    is_daytime=True,
                )
            ]
        },
    )
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    hass.states.async_set(
        "sensor.forecast",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=16.9,
                )
            ]
        },
    )
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("style", "config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "forecast_daily": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_MODERN_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "forecast_daily": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_MODERN_REQUIRED,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_weather")
async def test_forecasts_invalid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid forecasts."""
    expected = {TEST_WEATHER.entity_id: {"forecast": []}}

    # Test valid keys
    hass.states.async_set(
        "sensor.forecast_daily",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                    not_correct=1,
                )
            ]
        },
    )
    hass.states.async_set(
        "sensor.forecast_hourly",
        "sunny",
        {ATTR_FORECAST: None},
    )
    await hass.async_block_till_done()
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == expected

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == expected
    assert "Only valid keys in Forecast are allowed" in caplog.text

    # Test twice daily missing is_daytime
    hass.states.async_set(
        "sensor.forecast_twice_daily",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    datetime="2023-02-17T14:00:00+00:00",
                    temperature=14.2,
                )
            ]
        },
    )
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == expected
    assert "`is_daytime` is missing in twice_daily forecast" in caplog.text

    # Test twice daily missing datetime
    hass.states.async_set(
        "sensor.forecast_twice_daily",
        "sunny",
        {
            ATTR_FORECAST: [
                Forecast(
                    condition="cloudy",
                    temperature=14.2,
                    is_daytime=True,
                )
            ]
        },
    )
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == expected
    assert "`datetime` is required in forecasts" in caplog.text


@pytest.mark.parametrize(
    ("style", "config"),
    [
        (
            ConfigurationStyle.LEGACY,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "forecast_daily_template": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly_template": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily_template": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_LEGACY_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.MODERN,
            {
                "forecast_daily": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_MODERN_REQUIRED,
            },
        ),
        (
            ConfigurationStyle.TRIGGER,
            {
                "forecast_daily": "{{ state_attr('sensor.forecast_daily', 'forecast') }}",
                "forecast_hourly": "{{ state_attr('sensor.forecast_hourly', 'forecast') }}",
                "forecast_twice_daily": "{{ state_attr('sensor.forecast_twice_daily', 'forecast') }}",
                **TEST_MODERN_REQUIRED,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_weather")
async def test_forecast_format_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test forecast service invalid on incorrect format."""

    hass.states.async_set(
        "sensor.forecast_daily",
        "sunny",
        {
            ATTR_FORECAST: [
                "cloudy",
                "2023-02-17T14:00:00+00:00",
                14.2,
                1,
            ]
        },
    )
    hass.states.async_set(
        "sensor.forecast_hourly",
        "sunny",
        {
            ATTR_FORECAST: {
                "condition": "cloudy",
                "temperature": 14.2,
                "is_daytime": True,
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert "Forecast in list is not a dict, see Weather documentation" in caplog.text
    await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"entity_id": TEST_WEATHER.entity_id, "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert "Forecasts is not a list, see Weather documentation" in caplog.text


SAVED_EXTRA_DATA = {
    "last_apparent_temperature": None,
    "last_cloud_coverage": None,
    "last_dew_point": None,
    "last_forecast": None,
    "last_humidity": 10,
    "last_ozone": None,
    "last_pressure": None,
    "last_temperature": 20,
    "last_uv_index": None,
    "last_visibility": None,
    "last_wind_bearing": None,
    "last_wind_gust_speed": None,
    "last_wind_speed": None,
}

SAVED_EXTRA_DATA_WITH_FUTURE_KEY = {
    "last_apparent_temperature": None,
    "last_cloud_coverage": None,
    "last_dew_point": None,
    "last_forecast": None,
    "last_humidity": 10,
    "last_ozone": None,
    "last_pressure": None,
    "last_temperature": 20,
    "last_uv_index": None,
    "last_visibility": None,
    "last_wind_bearing": None,
    "last_wind_gust_speed": None,
    "last_wind_speed": None,
    "some_key_added_in_the_future": 123,
}


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "weather": {
                    "name": "test",
                    "condition_template": "{{ trigger.event.data.condition }}",
                    "temperature_template": "{{ trigger.event.data.temperature | float }}",
                    "temperature_unit": "°C",
                    "humidity_template": "{{ trigger.event.data.humidity | float }}",
                },
            },
        },
    ],
)
@pytest.mark.parametrize(
    ("saved_state", "saved_extra_data", "initial_state"),
    [
        ("sunny", SAVED_EXTRA_DATA, "sunny"),
        ("sunny", SAVED_EXTRA_DATA_WITH_FUTURE_KEY, "sunny"),
        (STATE_UNAVAILABLE, SAVED_EXTRA_DATA, STATE_UNKNOWN),
        (STATE_UNKNOWN, SAVED_EXTRA_DATA, STATE_UNKNOWN),
    ],
)
async def test_trigger_entity_restore_state(
    hass: HomeAssistant,
    count: int,
    domain: str,
    config: dict,
    saved_state: str,
    saved_extra_data: dict | None,
    initial_state: str,
) -> None:
    """Test restoring trigger template weather."""

    restored_attributes = {  # These should be ignored
        "temperature": -10,
        "humidity": 50,
    }

    fake_state = State(
        "weather.test",
        saved_state,
        restored_attributes,
    )
    mock_restore_cache_with_extra_data(hass, ((fake_state, saved_extra_data),))
    with assert_setup_component(count, domain):
        assert await async_setup_component(
            hass,
            domain,
            config,
        )

        await hass.async_block_till_done()
        await hass.async_start()
        await hass.async_block_till_done()

    state = hass.states.get("weather.test")
    assert state.state == initial_state

    hass.bus.async_fire(
        "test_event", {"condition": "cloudy", "temperature": 15, "humidity": 25}
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.test")

    state = hass.states.get("weather.test")
    assert state.state == "cloudy"
    assert state.attributes["temperature"] == 15.0
    assert state.attributes["humidity"] == 25.0


@pytest.mark.parametrize(("count", "domain"), [(1, "template")])
@pytest.mark.parametrize(
    "config",
    [
        {
            "template": [
                {
                    "unique_id": "listening-test-event",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [
                        {
                            "variables": {
                                "my_variable": "{{ trigger.event.data.temperature + 1 }}"
                            },
                        },
                    ],
                    "weather": [
                        {
                            "name": "Hello Name",
                            "condition_template": "sunny",
                            "temperature_unit": "°C",
                            "humidity_template": "{{ 20 }}",
                            "temperature_template": "{{ my_variable + 1 }}",
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_trigger_action(hass: HomeAssistant) -> None:
    """Test trigger entity with an action works."""
    state = hass.states.get("weather.hello_name")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    hass.bus.async_fire("test_event", {"temperature": 1}, context=context)
    await hass.async_block_till_done()

    state = hass.states.get("weather.hello_name")
    assert state.state == "sunny"
    assert state.attributes["temperature"] == 3.0
    assert state.context is context


async def test_restore_weather_save_state(
    hass: HomeAssistant, hass_storage: dict[str, Any], snapshot: SnapshotAssertion
) -> None:
    """Test Restore saved state for Weather trigger template."""
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "weather": {
                    "name": "test",
                    "condition_template": "{{ trigger.event.data.condition }}",
                    "temperature_template": "{{ trigger.event.data.temperature | float }}",
                    "temperature_unit": "°C",
                    "humidity_template": "{{ trigger.event.data.humidity | float }}",
                },
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.bus.async_fire(
        "test_event", {"condition": "cloudy", "temperature": 15, "humidity": 25}
    )
    await hass.async_block_till_done()
    entity = hass.states.get("weather.test")

    # Trigger saving state
    await async_mock_restore_state_shutdown_restart(hass)

    assert len(hass_storage[RESTORE_STATE_KEY]["data"]) == 1
    state = hass_storage[RESTORE_STATE_KEY]["data"][0]["state"]
    assert state["entity_id"] == entity.entity_id
    extra_data = hass_storage[RESTORE_STATE_KEY]["data"][0]["extra_data"]
    assert extra_data == snapshot


SAVED_ATTRIBUTES_1 = {
    "humidity": 20,
    "temperature": 10,
}

SAVED_EXTRA_DATA_MISSING_KEY = {
    "last_cloud_coverage": None,
    "last_dew_point": None,
    "last_humidity": 20,
    "last_ozone": None,
    "last_pressure": None,
    "last_temperature": 20,
    "last_uv_index": None,
    "last_visibility": None,
    "last_wind_bearing": None,
    "last_wind_gust_speed": None,
    "last_wind_speed": None,
}

SAVED_EXTRA_DATA_STRING_HUMIDITY = {
    "last_apparent_temperature": None,
    "last_cloud_coverage": None,
    "last_dew_point": None,
    "last_humidity": "20.0",
    "last_ozone": None,
    "last_pressure": None,
    "last_temperature": 20.0,
    "last_uv_index": None,
    "last_visibility": None,
    "last_wind_bearing": None,
    "last_wind_gust_speed": None,
    "last_wind_speed": None,
}


@pytest.mark.parametrize(
    ("saved_attributes", "saved_extra_data"),
    [
        (SAVED_ATTRIBUTES_1, SAVED_EXTRA_DATA_MISSING_KEY),
        (SAVED_ATTRIBUTES_1, SAVED_EXTRA_DATA_STRING_HUMIDITY),
        (SAVED_ATTRIBUTES_1, None),
    ],
)
async def test_trigger_entity_restore_state_fail(
    hass: HomeAssistant,
    saved_attributes: dict,
    saved_extra_data: dict | None,
) -> None:
    """Test restoring trigger template weather fails due to missing attribute."""

    saved_state = State(
        "weather.test",
        None,
        saved_attributes,
    )
    mock_restore_cache_with_extra_data(hass, ((saved_state, saved_extra_data),))
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "weather": {
                    "name": "test",
                    "condition_template": "{{ trigger.event.data.condition }}",
                    "temperature_template": "{{ trigger.event.data.temperature | float }}",
                    "temperature_unit": "°C",
                    "humidity_template": "{{ trigger.event.data.humidity | float }}",
                },
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("weather.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("temperature") is None


@pytest.mark.parametrize(
    ("style", "initial_expected_state"),
    [(ConfigurationStyle.MODERN, ""), (ConfigurationStyle.TRIGGER, None)],
)
@pytest.mark.parametrize(
    ("config", "attribute", "expected"),
    [
        (
            {
                CONF_ICON: "{% if states.weather.test_state.state == 'sunny' %}mdi:check{% endif %}",
                **TEST_LEGACY_REQUIRED,
            },
            ATTR_ICON,
            "mdi:check",
        ),
        (
            {
                CONF_PICTURE: "{% if states.weather.test_state.state == 'sunny' %}check.jpg{% endif %}",
                **TEST_LEGACY_REQUIRED,
            },
            ATTR_ENTITY_PICTURE,
            "check.jpg",
        ),
    ],
)
@pytest.mark.usefixtures("setup_weather")
async def test_templated_optional_config(
    hass: HomeAssistant,
    attribute: str,
    expected: str,
    initial_expected_state: str | None,
) -> None:
    """Test optional config templates."""
    state = hass.states.get(TEST_WEATHER.entity_id)
    assert state.attributes.get(attribute) == initial_expected_state

    state = hass.states.async_set(TEST_STATE_ENTITY_ID, "sunny")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_WEATHER.entity_id)

    assert state.attributes[attribute] == expected


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a weather from a config entry."""

    hass.states.async_set(
        "weather.test_state",
        "sunny",
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "condition": "{{ states('sensor.test_sensor') }}",
            "humidity": "{{ 50 }}",
            "temperature": "{{ 20 }}",
            "template_type": WEATHER_DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("weather.my_template")
    assert state is not None
    assert state == snapshot


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        WEATHER_DOMAIN,
        {
            "name": "My template",
            "condition": "{{ 'sunny' }}",
            "humidity": "{{ 50 }}",
            "temperature": "{{ 20 }}",
        },
    )

    assert state["state"] == "sunny"
