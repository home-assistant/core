"""Tests for the fitbit sensor platform."""


from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import PROFILE_USER_ID, timeseries_response

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

    state = hass.states.get(entity_id)
    assert state
    entry = entity_registry.async_get(entity_id)
    assert entry
    assert (state.state, state.attributes, entry.unique_id) == snapshot


@pytest.mark.parametrize(
    ("devices_response", "monitored_resources"),
    [([DEVICE_RESPONSE_CHARGE_2, DEVICE_RESPONSE_ARIA_AIR], ["devices/battery"])],
)
async def test_device_battery_level(
    hass: HomeAssistant,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test battery level sensor for devices."""

    await sensor_platform_setup()

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

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("sensor.aria_air_battery")
    assert entry
    assert entry.unique_id == f"{PROFILE_USER_ID}_devices/battery_016713257"


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
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
    expected_unit: str,
) -> None:
    """Test the fitbit profile locale impact on unit of measure."""

    register_timeseries("body/weight", timeseries_response("body-weight", "175"))
    await sensor_platform_setup()

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
