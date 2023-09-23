"""Tests for the fitbit sensor platform."""


from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from homeassistant.core import HomeAssistant

from .conftest import timeseries_response

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
    "monitored_resources",
    [["activities/steps"]],
)
async def test_step_sensor(
    hass: HomeAssistant,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
    register_timeseries: Callable[[str, dict[str, Any]], None],
) -> None:
    """Test battery level sensor."""

    register_timeseries(
        "activities/steps", timeseries_response("activities-steps", "5600")
    )
    await sensor_platform_setup()

    state = hass.states.get("sensor.steps")
    assert state
    assert state.state == "5600"
    assert state.attributes == {
        "attribution": "Data provided by Fitbit.com",
        "friendly_name": "Steps",
        "icon": "mdi:walk",
        "unit_of_measurement": "steps",
    }


@pytest.mark.parametrize(
    ("devices_response", "monitored_resources"),
    [([DEVICE_RESPONSE_CHARGE_2, DEVICE_RESPONSE_ARIA_AIR], ["devices/battery"])],
)
async def test_device_battery_level(
    hass: HomeAssistant,
    sensor_platform_setup: Callable[[], Awaitable[bool]],
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
