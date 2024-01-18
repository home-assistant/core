"""Tests for the fitbit sensor platform."""


from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests_mock.mocker import Mocker
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fitbit.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .conftest import (
    DEVICES_API_URL,
    PROFILE_USER_ID,
    SERVER_ACCESS_TOKEN,
    TIMESERIES_API_URL_FORMAT,
    timeseries_response,
)

from tests.common import MockConfigEntry

DEVICE_RESPONSE_CHARGE_2 = {
    "battery": "Medium",
    "batteryLevel": 60,
    "deviceVersion": "Charge 2",
    "id": "816713257",
    "lastSyncTime": "2019-11-07T12:00:58.000",
    "mac": "16ADD56D54GD",
    "type": "TRACKER",
}
DEVICE_RESPONSE_ARIA_AIR = {
    "battery": "High",
    "batteryLevel": 95,
    "deviceVersion": "Aria Air",
    "id": "016713257",
    "lastSyncTime": "2019-11-07T12:00:58.000",
    "mac": "06ADD56D54GD",
    "type": "SCALE",
}


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture(autouse=True)
def mock_token_refresh(requests_mock: Mocker) -> None:
    """Test that platform configuration is imported successfully."""

    requests_mock.register_uri(
        "POST",
        OAUTH2_TOKEN,
        status_code=HTTPStatus.OK,
        json=SERVER_ACCESS_TOKEN,
    )


@pytest.mark.parametrize(
    (
        "monitored_resources",
        "entity_id",
        "api_resource",
        "api_value",
    ),
    [
        (
            ["activities/activityCalories"],
            "sensor.activity_calories",
            "activities/activityCalories",
            "135",
        ),
        (
            ["activities/calories"],
            "sensor.calories",
            "activities/calories",
            "139",
        ),
        (
            ["activities/distance"],
            "sensor.distance",
            "activities/distance",
            "12.7",
        ),
        (
            ["activities/elevation"],
            "sensor.elevation",
            "activities/elevation",
            "7600.24",
        ),
        (
            ["activities/floors"],
            "sensor.floors",
            "activities/floors",
            "8",
        ),
        (
            ["activities/heart"],
            "sensor.resting_heart_rate",
            "activities/heart",
            {"restingHeartRate": 76},
        ),
        (
            ["activities/minutesFairlyActive"],
            "sensor.minutes_fairly_active",
            "activities/minutesFairlyActive",
            35,
        ),
        (
            ["activities/minutesLightlyActive"],
            "sensor.minutes_lightly_active",
            "activities/minutesLightlyActive",
            95,
        ),
        (
            ["activities/minutesSedentary"],
            "sensor.minutes_sedentary",
            "activities/minutesSedentary",
            18,
        ),
        (
            ["activities/minutesVeryActive"],
            "sensor.minutes_very_active",
            "activities/minutesVeryActive",
            20,
        ),
        (
            ["activities/steps"],
            "sensor.steps",
            "activities/steps",
            "5600",
        ),
        (
            ["body/weight"],
            "sensor.weight",
            "body/weight",
            "175",
        ),
        (
            ["body/fat"],
            "sensor.body_fat",
            "body/fat",
            "18",
        ),
        (
            ["body/bmi"],
            "sensor.bmi",
            "body/bmi",
            "23.7",
        ),
        (
            ["sleep/awakeningsCount"],
            "sensor.awakenings_count",
            "sleep/awakeningsCount",
            "7",
        ),
        (
            ["sleep/efficiency"],
            "sensor.sleep_efficiency",
            "sleep/efficiency",
            "80",
        ),
        (
            ["sleep/minutesAfterWakeup"],
            "sensor.minutes_after_wakeup",
            "sleep/minutesAfterWakeup",
            "17",
        ),
        (
            ["sleep/minutesAsleep"],
            "sensor.sleep_minutes_asleep",
            "sleep/minutesAsleep",
            "360",
        ),
        (
            ["sleep/minutesAwake"],
            "sensor.sleep_minutes_awake",
            "sleep/minutesAwake",
            "35",
        ),
        (
            ["sleep/minutesToFallAsleep"],
            "sensor.sleep_minutes_to_fall_asleep",
            "sleep/minutesToFallAsleep",
            "35",
        ),
        (
            ["sleep/startTime"],
            "sensor.sleep_start_time",
            "sleep/startTime",
            "2020-01-27T00:17:30.000",
        ),
        (
            ["sleep/timeInBed"],
            "sensor.sleep_time_in_bed",
            "sleep/timeInBed",
            "462",
        ),
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
    entity_registry: er.EntityRegistry,
    entity_id: str,
    api_resource: str,
    api_value: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors."""

    register_timeseries(
        api_resource, timeseries_response(api_resource.replace("/", "-"), api_value)
    )
    await sensor_platform_setup()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    state = hass.states.get(entity_id)
    assert state
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert (state.state, state.attributes, entry.unique_id) == snapshot


@pytest.mark.parametrize(
    ("devices_response", "monitored_resources"),
    [([DEVICE_RESPONSE_CHARGE_2, DEVICE_RESPONSE_ARIA_AIR], ["devices/battery"])],
)
async def test_device_battery(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test battery level sensor for devices."""

    assert await sensor_platform_setup()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    state = hass.states.get("sensor.charge_2_battery")
    assert state
    assert state.state == "Medium"
    assert state.attributes == {
        "attribution": "Data provided by Fitbit.com",
        "friendly_name": "Charge 2 Battery",
        "icon": "mdi:battery-50",
        "model": "Charge 2",
        "type": "tracker",
    }

    entry = entity_registry.async_get("sensor.charge_2_battery")
    assert entry
    assert entry.unique_id == f"{PROFILE_USER_ID}_devices/battery_816713257"

    state = hass.states.get("sensor.aria_air_battery")
    assert state
    assert state.state == "High"
    assert state.attributes == {
        "attribution": "Data provided by Fitbit.com",
        "friendly_name": "Aria Air Battery",
        "icon": "mdi:battery",
        "model": "Aria Air",
        "type": "scale",
    }

    entry = entity_registry.async_get("sensor.aria_air_battery")
    assert entry
    assert entry.unique_id == f"{PROFILE_USER_ID}_devices/battery_016713257"


@pytest.mark.parametrize(
    ("devices_response", "monitored_resources"),
    [([DEVICE_RESPONSE_CHARGE_2, DEVICE_RESPONSE_ARIA_AIR], ["devices/battery"])],
)
async def test_device_battery_level(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test battery level sensor for devices."""

    assert await sensor_platform_setup()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    state = hass.states.get("sensor.charge_2_battery_level")
    assert state
    assert state.state == "60"
    assert state.attributes == {
        "attribution": "Data provided by Fitbit.com",
        "friendly_name": "Charge 2 Battery level",
        "device_class": "battery",
        "unit_of_measurement": "%",
    }

    state = hass.states.get("sensor.aria_air_battery_level")
    assert state
    assert state.state == "95"
    assert state.attributes == {
        "attribution": "Data provided by Fitbit.com",
        "friendly_name": "Aria Air Battery level",
        "device_class": "battery",
        "unit_of_measurement": "%",
    }


@pytest.mark.parametrize(
    (
        "monitored_resources",
        "profile_locale",
        "configured_unit_system",
        "expected_unit",
    ),
    [
        # Defaults to home assistant unit system unless UK
        (["body/weight"], "en_US", "default", "kg"),
        (["body/weight"], "en_GB", "default", "st"),
        (["body/weight"], "es_ES", "default", "kg"),
        # Use the configured unit system from yaml
        (["body/weight"], "en_US", "en_US", "lb"),
        (["body/weight"], "en_GB", "en_US", "lb"),
        (["body/weight"], "es_ES", "en_US", "lb"),
        (["body/weight"], "en_US", "en_GB", "st"),
        (["body/weight"], "en_GB", "en_GB", "st"),
        (["body/weight"], "es_ES", "en_GB", "st"),
        (["body/weight"], "en_US", "metric", "kg"),
        (["body/weight"], "en_GB", "metric", "kg"),
        (["body/weight"], "es_ES", "metric", "kg"),
    ],
)
async def test_profile_local(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
    expected_unit: str,
) -> None:
    """Test the fitbit profile locale impact on unit of measure."""

    register_timeseries("body/weight", timeseries_response("body-weight", "175"))
    await sensor_platform_setup()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    state = hass.states.get("sensor.weight")
    assert state
    assert state.attributes.get("unit_of_measurement") == expected_unit


@pytest.mark.parametrize(
    ("sensor_platform_config", "api_response", "expected_state"),
    [
        (
            {"clock_format": "12H", "monitored_resources": ["sleep/startTime"]},
            "17:05",
            "5:05 PM",
        ),
        (
            {"clock_format": "12H", "monitored_resources": ["sleep/startTime"]},
            "5:05",
            "5:05 AM",
        ),
        (
            {"clock_format": "12H", "monitored_resources": ["sleep/startTime"]},
            "00:05",
            "12:05 AM",
        ),
        (
            {"clock_format": "24H", "monitored_resources": ["sleep/startTime"]},
            "17:05",
            "17:05",
        ),
        (
            {"clock_format": "12H", "monitored_resources": ["sleep/startTime"]},
            "",
            "-",
        ),
    ],
)
async def test_sleep_time_clock_format(
    hass: HomeAssistant,
    fitbit_config_setup: None,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
    api_response: str,
    expected_state: str,
) -> None:
    """Test the clock format configuration."""

    register_timeseries(
        "sleep/startTime", timeseries_response("sleep-startTime", api_response)
    )
    await sensor_platform_setup()

    state = hass.states.get("sensor.sleep_start_time")
    assert state
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("scopes"),
    [(["activity"])],
)
async def test_activity_scope_config_entry(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
) -> None:
    """Test activity sensors are enabled."""

    for api_resource in (
        "activities/activityCalories",
        "activities/calories",
        "activities/distance",
        "activities/elevation",
        "activities/floors",
        "activities/minutesFairlyActive",
        "activities/minutesLightlyActive",
        "activities/minutesSedentary",
        "activities/minutesVeryActive",
        "activities/steps",
    ):
        register_timeseries(
            api_resource, timeseries_response(api_resource.replace("/", "-"), "0")
        )
    assert await integration_setup()

    states = hass.states.async_all()
    assert {s.entity_id for s in states} == {
        "sensor.activity_calories",
        "sensor.calories",
        "sensor.distance",
        "sensor.elevation",
        "sensor.floors",
        "sensor.minutes_fairly_active",
        "sensor.minutes_lightly_active",
        "sensor.minutes_sedentary",
        "sensor.minutes_very_active",
        "sensor.steps",
    }


@pytest.mark.parametrize(
    ("scopes"),
    [(["heartrate"])],
)
async def test_heartrate_scope_config_entry(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
) -> None:
    """Test heartrate sensors are enabled."""

    register_timeseries(
        "activities/heart",
        timeseries_response("activities-heart", {"restingHeartRate": "0"}),
    )
    assert await integration_setup()

    states = hass.states.async_all()
    assert {s.entity_id for s in states} == {
        "sensor.resting_heart_rate",
    }


@pytest.mark.parametrize(
    ("scopes", "unit_system"),
    [(["nutrition"], METRIC_SYSTEM), (["nutrition"], US_CUSTOMARY_SYSTEM)],
)
async def test_nutrition_scope_config_entry(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
    unit_system: UnitSystem,
    snapshot: SnapshotAssertion,
) -> None:
    """Test nutrition sensors are enabled."""
    hass.config.units = unit_system
    register_timeseries(
        "foods/log/water",
        timeseries_response("foods-log-water", "99"),
    )
    register_timeseries(
        "foods/log/caloriesIn",
        timeseries_response("foods-log-caloriesIn", "1600"),
    )
    assert await integration_setup()

    state = hass.states.get("sensor.water")
    assert state
    assert (state.state, state.attributes) == snapshot

    state = hass.states.get("sensor.calories_in")
    assert state
    assert (state.state, state.attributes) == snapshot


@pytest.mark.parametrize(
    ("scopes"),
    [(["sleep"])],
)
async def test_sleep_scope_config_entry(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
) -> None:
    """Test sleep sensors are enabled."""

    for api_resource in (
        "sleep/startTime",
        "sleep/timeInBed",
        "sleep/minutesToFallAsleep",
        "sleep/minutesAwake",
        "sleep/minutesAsleep",
        "sleep/minutesAfterWakeup",
        "sleep/efficiency",
        "sleep/awakeningsCount",
    ):
        register_timeseries(
            api_resource,
            timeseries_response(api_resource.replace("/", "-"), "0"),
        )
    assert await integration_setup()

    states = hass.states.async_all()
    assert {s.entity_id for s in states} == {
        "sensor.awakenings_count",
        "sensor.sleep_efficiency",
        "sensor.minutes_after_wakeup",
        "sensor.sleep_minutes_asleep",
        "sensor.sleep_minutes_awake",
        "sensor.sleep_minutes_to_fall_asleep",
        "sensor.sleep_time_in_bed",
        "sensor.sleep_start_time",
    }


@pytest.mark.parametrize(
    ("scopes"),
    [(["weight"])],
)
async def test_weight_scope_config_entry(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
) -> None:
    """Test sleep sensors are enabled."""

    register_timeseries("body/weight", timeseries_response("body-weight", "0"))
    assert await integration_setup()

    states = hass.states.async_all()
    assert [s.entity_id for s in states] == [
        "sensor.weight",
    ]


@pytest.mark.parametrize(
    ("scopes", "devices_response"),
    [(["settings"], [DEVICE_RESPONSE_CHARGE_2])],
)
async def test_settings_scope_config_entry(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
) -> None:
    """Test device sensors are enabled."""

    assert await integration_setup()

    states = hass.states.async_all()
    assert [s.entity_id for s in states] == [
        "sensor.charge_2_battery",
        "sensor.charge_2_battery_level",
    ]


@pytest.mark.parametrize(
    ("scopes", "request_condition"),
    [
        (["heartrate"], {"status_code": HTTPStatus.INTERNAL_SERVER_ERROR}),
        (["heartrate"], {"status_code": HTTPStatus.BAD_REQUEST}),
        (["heartrate"], {"exc": RequestsConnectionError}),
    ],
)
async def test_sensor_update_failed(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    requests_mock: Mocker,
    request_condition: dict[str, Any],
) -> None:
    """Test a failed sensor update when talking to the API."""

    requests_mock.register_uri(
        "GET",
        TIMESERIES_API_URL_FORMAT.format(resource="activities/heart"),
        **request_condition,
    )

    assert await integration_setup()

    state = hass.states.get("sensor.resting_heart_rate")
    assert state
    assert state.state == "unavailable"

    # Verify the config entry is in a normal state (no reauth required)
    flows = hass.config_entries.flow.async_progress()
    assert not flows


@pytest.mark.parametrize(
    ("scopes"),
    [(["heartrate"])],
)
async def test_sensor_update_failed_requires_reauth(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    requests_mock: Mocker,
) -> None:
    """Test a sensor update request requires reauth."""

    requests_mock.register_uri(
        "GET",
        TIMESERIES_API_URL_FORMAT.format(resource="activities/heart"),
        status_code=HTTPStatus.UNAUTHORIZED,
        json={
            "errors": [{"errorType": "invalid_grant"}],
        },
    )

    assert await integration_setup()

    state = hass.states.get("sensor.resting_heart_rate")
    assert state
    assert state.state == "unavailable"

    # Verify that reauth is required
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    ("scopes"),
    [(["heartrate"])],
)
async def test_sensor_update_success(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    requests_mock: Mocker,
) -> None:
    """Test API failure for a battery level sensor for devices."""

    requests_mock.register_uri(
        "GET",
        TIMESERIES_API_URL_FORMAT.format(resource="activities/heart"),
        [
            {
                "status_code": HTTPStatus.OK,
                "json": timeseries_response(
                    "activities-heart", {"restingHeartRate": "60"}
                ),
            },
            {
                "status_code": HTTPStatus.OK,
                "json": timeseries_response(
                    "activities-heart", {"restingHeartRate": "70"}
                ),
            },
        ],
    )

    assert await integration_setup()

    state = hass.states.get("sensor.resting_heart_rate")
    assert state
    assert state.state == "60"

    await async_update_entity(hass, "sensor.resting_heart_rate")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.resting_heart_rate")
    assert state
    assert state.state == "70"


@pytest.mark.parametrize(
    ("scopes", "mock_devices"),
    [(["settings"], None)],
)
async def test_device_battery_level_update_failed(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    requests_mock: Mocker,
) -> None:
    """Test API failure for a battery level sensor for devices."""

    requests_mock.register_uri(
        "GET",
        DEVICES_API_URL,
        [
            {
                "status_code": HTTPStatus.OK,
                "json": [DEVICE_RESPONSE_CHARGE_2],
            },
            # Fail when requesting an update
            {
                "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
                "json": {
                    "errors": [
                        {
                            "errorType": "request",
                            "message": "An error occurred",
                        }
                    ]
                },
            },
        ],
    )

    assert await integration_setup()

    state = hass.states.get("sensor.charge_2_battery")
    assert state
    assert state.state == "Medium"

    # Request an update for the entity which will fail
    await async_update_entity(hass, "sensor.charge_2_battery")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.charge_2_battery")
    assert state
    assert state.state == "unavailable"

    # Verify the config entry is in a normal state (no reauth required)
    flows = hass.config_entries.flow.async_progress()
    assert not flows


@pytest.mark.parametrize(
    ("scopes", "mock_devices"),
    [(["settings"], None)],
)
async def test_device_battery_level_reauth_required(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    requests_mock: Mocker,
) -> None:
    """Test API failure requires reauth."""

    requests_mock.register_uri(
        "GET",
        DEVICES_API_URL,
        [
            {
                "status_code": HTTPStatus.OK,
                "json": [DEVICE_RESPONSE_CHARGE_2],
            },
            # Fail when requesting an update
            {
                "status_code": HTTPStatus.UNAUTHORIZED,
                "json": {
                    "errors": [{"errorType": "invalid_grant"}],
                },
            },
        ],
    )

    assert await integration_setup()

    state = hass.states.get("sensor.charge_2_battery")
    assert state
    assert state.state == "Medium"

    # Request an update for the entity which will fail
    await async_update_entity(hass, "sensor.charge_2_battery")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.charge_2_battery")
    assert state
    assert state.state == "unavailable"

    # Verify that reauth is required
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    ("scopes", "response_data", "expected_state"),
    [
        (["heartrate"], {}, "unknown"),
        (
            ["heartrate"],
            {
                "restingHeartRate": 120,
            },
            "120",
        ),
        (
            ["heartrate"],
            {
                "restingHeartRate": 0,
            },
            "0",
        ),
    ],
    ids=("missing", "valid", "zero"),
)
async def test_resting_heart_rate_responses(
    hass: HomeAssistant,
    setup_credentials: None,
    integration_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
    response_data: dict[str, Any],
    expected_state: str,
) -> None:
    """Test resting heart rate sensor with various values from response."""

    register_timeseries(
        "activities/heart",
        timeseries_response(
            "activities-heart",
            {
                "customHeartRateZones": [],
                "heartRateZones": [
                    {
                        "caloriesOut": 0,
                        "max": 220,
                        "min": 159,
                        "minutes": 0,
                        "name": "Peak",
                    },
                ],
                **response_data,
            },
        ),
    )
    assert await integration_setup()

    state = hass.states.get("sensor.resting_heart_rate")
    assert state
    assert state.state == expected_state
