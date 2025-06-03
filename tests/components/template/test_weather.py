"""The tests for the Template Weather platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.weather import (
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
    Forecast,
)
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, HomeAssistant, State
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    assert_setup_component,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache_with_extra_data,
)

ATTR_FORECAST = "forecast"


@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {"weather": {"platform": "demo"}},
                {
                    "platform": "template",
                    "name": "test",
                    "attribution_template": "{{ states('sensor.attribution') }}",
                    "condition_template": "sunny",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                    "pressure_template": "{{ states('sensor.pressure') }}",
                    "wind_speed_template": "{{ states('sensor.windspeed') }}",
                    "wind_bearing_template": "{{ states('sensor.windbearing') }}",
                    "ozone_template": "{{ states('sensor.ozone') }}",
                    "visibility_template": "{{ states('sensor.visibility') }}",
                    "wind_gust_speed_template": "{{ states('sensor.wind_gust_speed') }}",
                    "cloud_coverage_template": "{{ states('sensor.cloud_coverage') }}",
                    "dew_point_template": "{{ states('sensor.dew_point') }}",
                    "apparent_temperature_template": "{{ states('sensor.apparent_temperature') }}",
                },
            ]
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template."""
    for attr, v_attr, value in (
        (
            "sensor.attribution",
            ATTR_ATTRIBUTION,
            "The custom attribution",
        ),
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
        ("sensor.pressure", ATTR_WEATHER_PRESSURE, 1000),
        ("sensor.windspeed", ATTR_WEATHER_WIND_SPEED, 20),
        ("sensor.windbearing", ATTR_WEATHER_WIND_BEARING, 180),
        ("sensor.ozone", ATTR_WEATHER_OZONE, 25),
        ("sensor.visibility", ATTR_WEATHER_VISIBILITY, 4.6),
        ("sensor.wind_gust_speed", ATTR_WEATHER_WIND_GUST_SPEED, 30),
        ("sensor.cloud_coverage", ATTR_WEATHER_CLOUD_COVERAGE, 75),
        ("sensor.dew_point", ATTR_WEATHER_DEW_POINT, 2.2),
        ("sensor.apparent_temperature", ATTR_WEATHER_APPARENT_TEMPERATURE, 25),
    ):
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()
        state = hass.states.get("weather.test")
        assert state is not None
        assert state.state == "sunny"
        assert state.attributes.get(v_attr) == value


@pytest.mark.parametrize(
    ("service"),
    [SERVICE_GET_FORECASTS],
)
@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_daily_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_hourly_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_twice_daily_template": "{{ states.weather.forecast_twice_daily.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_forecasts(
    hass: HomeAssistant, snapshot: SnapshotAssertion, service: str
) -> None:
    """Test forecast service."""
    for attr, _v_attr, value in (
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ):
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast",
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
        "weather.forecast_twice_daily",
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
    state = hass.states.get("weather.forecast")
    assert state is not None
    assert state.state == "sunny"
    state2 = hass.states.get("weather.forecast_twice_daily")
    assert state2 is not None
    assert state2.state == "fog"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    hass.states.async_set(
        "weather.forecast",
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
    state = hass.states.get("weather.forecast")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        (SERVICE_GET_FORECASTS, {"weather.forecast": {"forecast": []}}),
    ],
)
@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_daily_template": "{{ states.weather.forecast.attributes.forecast }}",
                    "forecast_hourly_template": "{{ states.weather.forecast_hourly.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_forecast_invalid(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    service: str,
    expected: dict[str, Any],
) -> None:
    """Test invalid forecasts."""
    for attr, _v_attr, value in (
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ):
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast",
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
        "weather.forecast_hourly",
        "sunny",
        {ATTR_FORECAST: None},
    )
    await hass.async_block_till_done()
    state = hass.states.get("weather.forecast_hourly")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert response == expected
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert response == expected
    assert "Only valid keys in Forecast are allowed" in caplog.text


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        (SERVICE_GET_FORECASTS, {"weather.forecast": {"forecast": []}}),
    ],
)
@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_twice_daily_template": "{{ states.weather.forecast_twice_daily.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_forecast_invalid_is_daytime_missing_in_twice_daily(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    service: str,
    expected: dict[str, Any],
) -> None:
    """Test forecast service invalid when is_daytime missing in twice_daily forecast."""
    for attr, _v_attr, value in (
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ):
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast_twice_daily",
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
    state = hass.states.get("weather.forecast_twice_daily")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == expected
    assert "`is_daytime` is missing in twice_daily forecast" in caplog.text


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        (SERVICE_GET_FORECASTS, {"weather.forecast": {"forecast": []}}),
    ],
)
@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_twice_daily_template": "{{ states.weather.forecast_twice_daily.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_forecast_invalid_datetime_missing(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    service: str,
    expected: dict[str, Any],
) -> None:
    """Test forecast service invalid when datetime missing."""
    for attr, _v_attr, value in (
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ):
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast_twice_daily",
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
    state = hass.states.get("weather.forecast_twice_daily")
    assert state is not None
    assert state.state == "sunny"

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "twice_daily"},
        blocking=True,
        return_response=True,
    )
    assert response == expected
    assert "`datetime` is required in forecasts" in caplog.text


@pytest.mark.parametrize(
    ("service"),
    [SERVICE_GET_FORECASTS],
)
@pytest.mark.parametrize(("count", "domain"), [(1, WEATHER_DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            "weather": [
                {
                    "platform": "template",
                    "name": "forecast",
                    "condition_template": "sunny",
                    "forecast_daily_template": "{{ states.weather.forecast_daily.attributes.forecast }}",
                    "forecast_hourly_template": "{{ states.weather.forecast_hourly.attributes.forecast }}",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                },
            ]
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_forecast_format_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, service: str
) -> None:
    """Test forecast service invalid on incorrect format."""
    for attr, _v_attr, value in (
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
    ):
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()

    hass.states.async_set(
        "weather.forecast_daily",
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
        "weather.forecast_hourly",
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
        service,
        {"entity_id": "weather.forecast", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    assert "Forecasts is not a list, see Weather documentation" in caplog.text
    await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {"entity_id": "weather.forecast", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    assert "Forecast in list is not a dict, see Weather documentation" in caplog.text


SAVED_EXTRA_DATA = {
    "last_apparent_temperature": None,
    "last_cloud_coverage": None,
    "last_dew_point": None,
    "last_forecast": None,
    "last_humidity": 10,
    "last_ozone": None,
    "last_pressure": None,
    "last_temperature": 20,
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


@pytest.mark.parametrize(
    ("service"),
    [SERVICE_GET_FORECASTS],
)
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
                                "my_variable": "{{ trigger.event.data.information + 1 }}",
                                "var_forecast_daily": "{{ trigger.event.data.forecast_daily }}",
                                "var_forecast_hourly": "{{ trigger.event.data.forecast_hourly }}",
                                "var_forecast_twice_daily": "{{ trigger.event.data.forecast_twice_daily }}",
                            },
                        },
                    ],
                    "weather": [
                        {
                            "name": "Test",
                            "condition_template": "sunny",
                            "precipitation_unit": "mm",
                            "pressure_unit": "hPa",
                            "visibility_unit": "km",
                            "wind_speed_unit": "km/h",
                            "temperature_unit": "°C",
                            "temperature_template": "{{ my_variable + 1 }}",
                            "humidity_template": "{{ my_variable + 1 }}",
                            "wind_speed_template": "{{ my_variable + 1 }}",
                            "wind_bearing_template": "{{ my_variable + 1 }}",
                            "ozone_template": "{{ my_variable + 1 }}",
                            "visibility_template": "{{ my_variable + 1 }}",
                            "pressure_template": "{{ my_variable + 1 }}",
                            "wind_gust_speed_template": "{{ my_variable + 1 }}",
                            "cloud_coverage_template": "{{ my_variable + 1 }}",
                            "dew_point_template": "{{ my_variable + 1 }}",
                            "apparent_temperature_template": "{{ my_variable + 1 }}",
                            "forecast_daily_template": "{{ var_forecast_daily }}",
                            "forecast_hourly_template": "{{ var_forecast_hourly }}",
                            "forecast_twice_daily_template": "{{ var_forecast_twice_daily }}",
                        }
                    ],
                },
            ],
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
@pytest.mark.freeze_time("2023-10-19 13:50:05")
async def test_trigger_weather_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    service: str,
) -> None:
    """Test trigger weather entity with services."""
    state = hass.states.get("weather.test")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    context = Context()
    now = dt_util.now().isoformat()
    hass.bus.async_fire(
        "test_event",
        {
            "information": 1,
            "forecast_daily": [
                {
                    "datetime": now,
                    "condition": "sunny",
                    "precipitation": 20,
                    "temperature": 20,
                    "templow": 15,
                }
            ],
            "forecast_hourly": [
                {
                    "datetime": now,
                    "condition": "sunny",
                    "precipitation": 20,
                    "temperature": 20,
                    "templow": 15,
                }
            ],
            "forecast_twice_daily": [
                {
                    "datetime": now,
                    "condition": "sunny",
                    "precipitation": 20,
                    "temperature": 20,
                    "templow": 15,
                    "is_daytime": True,
                }
            ],
        },
        context=context,
    )
    await hass.async_block_till_done()

    state = hass.states.get("weather.test")
    assert state.state == "sunny"
    assert state.attributes["temperature"] == 3.0
    assert state.attributes["humidity"] == 3.0
    assert state.attributes["wind_speed"] == 3.0
    assert state.attributes["wind_bearing"] == 3.0
    assert state.attributes["ozone"] == 3.0
    assert state.attributes["visibility"] == 3.0
    assert state.attributes["pressure"] == 3.0
    assert state.attributes["wind_gust_speed"] == 3.0
    assert state.attributes["cloud_coverage"] == 3.0
    assert state.attributes["dew_point"] == 3.0
    assert state.attributes["apparent_temperature"] == 3.0
    assert state.context is context

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": state.entity_id,
            "type": "daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": state.entity_id,
            "type": "hourly",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot

    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        service,
        {
            "entity_id": state.entity_id,
            "type": "twice_daily",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


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
    "last_visibility": None,
    "last_wind_bearing": None,
    "last_wind_gust_speed": None,
    "last_wind_speed": None,
}


@pytest.mark.parametrize(
    ("saved_attributes", "saved_extra_data"),
    [
        (SAVED_ATTRIBUTES_1, SAVED_EXTRA_DATA_MISSING_KEY),
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


async def test_new_style_template_state_text(hass: HomeAssistant) -> None:
    """Test the state text of a template."""
    assert await async_setup_component(
        hass,
        "weather",
        {
            "weather": [
                {"weather": {"platform": "demo"}},
            ]
        },
    )
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": {
                "weather": {
                    "name": "test",
                    "attribution_template": "{{ states('sensor.attribution') }}",
                    "condition_template": "sunny",
                    "temperature_template": "{{ states('sensor.temperature') | float }}",
                    "humidity_template": "{{ states('sensor.humidity') | int }}",
                    "pressure_template": "{{ states('sensor.pressure') }}",
                    "wind_speed_template": "{{ states('sensor.windspeed') }}",
                    "wind_bearing_template": "{{ states('sensor.windbearing') }}",
                    "ozone_template": "{{ states('sensor.ozone') }}",
                    "visibility_template": "{{ states('sensor.visibility') }}",
                    "wind_gust_speed_template": "{{ states('sensor.wind_gust_speed') }}",
                    "cloud_coverage_template": "{{ states('sensor.cloud_coverage') }}",
                    "dew_point_template": "{{ states('sensor.dew_point') }}",
                    "apparent_temperature_template": "{{ states('sensor.apparent_temperature') }}",
                },
            },
        },
    )

    for attr, v_attr, value in (
        (
            "sensor.attribution",
            ATTR_ATTRIBUTION,
            "The custom attribution",
        ),
        ("sensor.temperature", ATTR_WEATHER_TEMPERATURE, 22.3),
        ("sensor.humidity", ATTR_WEATHER_HUMIDITY, 60),
        ("sensor.pressure", ATTR_WEATHER_PRESSURE, 1000),
        ("sensor.windspeed", ATTR_WEATHER_WIND_SPEED, 20),
        ("sensor.windbearing", ATTR_WEATHER_WIND_BEARING, 180),
        ("sensor.ozone", ATTR_WEATHER_OZONE, 25),
        ("sensor.visibility", ATTR_WEATHER_VISIBILITY, 4.6),
        ("sensor.wind_gust_speed", ATTR_WEATHER_WIND_GUST_SPEED, 30),
        ("sensor.cloud_coverage", ATTR_WEATHER_CLOUD_COVERAGE, 75),
        ("sensor.dew_point", ATTR_WEATHER_DEW_POINT, 2.2),
        ("sensor.apparent_temperature", ATTR_WEATHER_APPARENT_TEMPERATURE, 25),
    ):
        hass.states.async_set(attr, value)
        await hass.async_block_till_done()
        state = hass.states.get("weather.test")
        assert state is not None
        assert state.state == "sunny"
        assert state.attributes.get(v_attr) == value
