"""The tests for the Google Wifi sensor platform."""

from datetime import timedelta
from typing import Any

import aiohttp
import pytest

from homeassistant.components.google_wifi import const
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import RESOURCE_URL, UPDATED_RESPONSE

from tests.common import assert_setup_component, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

MONITORED_CONDITIONS = [
    const.ATTR_CURRENT_VERSION,
    const.ATTR_NEW_VERSION,
    const.ATTR_UPTIME,
    const.ATTR_LAST_RESTART,
    const.ATTR_LOCAL_IP,
    const.ATTR_STATUS,
]


async def setup_sensor_platform(
    hass: HomeAssistant,
    *,
    name: str | None = None,
    monitored_conditions: list[str] | None = None,
) -> None:
    """Set up the Google Wifi sensor platform with mocked data."""
    sensor_config: dict[str, Any] = {
        "platform": "google_wifi",
        "monitored_conditions": monitored_conditions or MONITORED_CONDITIONS,
    }
    if name is not None:
        sensor_config["name"] = name

    assert await async_setup_component(hass, "sensor", {"sensor": sensor_config})
    await hass.async_block_till_done()


async def fire_polling_update(hass: HomeAssistant, seconds: int) -> None:
    """Advance time far enough to trigger the coordinator update."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_success")
async def test_setup_minimum(hass: HomeAssistant) -> None:
    """Test setup with the minimum configuration."""
    await setup_sensor_platform(
        hass,
        monitored_conditions=[const.ATTR_UPTIME],
    )

    assert_setup_component(1, "sensor")
    state = hass.states.get("sensor.google_wifi_uptime")
    assert state is not None
    assert state.state == "1.0"


@pytest.mark.usefixtures("mock_success")
async def test_setup_get(hass: HomeAssistant) -> None:
    """Test setup with full configuration."""
    await setup_sensor_platform(
        hass,
        name="Test Wifi",
    )

    assert_setup_component(6, "sensor")
    assert hass.states.get("sensor.test_wifi_current_version") is not None


@pytest.mark.usefixtures("mock_unreachable")
async def test_setup_when_router_unreachable(hass: HomeAssistant) -> None:
    """Test platform setup completes when the router does not respond."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "google_wifi",
                "monitored_conditions": [const.ATTR_UPTIME],
            }
        },
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.google_wifi_uptime")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_success")
async def test_sensor_states_update_from_router_data(hass: HomeAssistant) -> None:
    """Test the entities expose the current router data through Home Assistant."""
    await setup_sensor_platform(
        hass,
        name="Test Wifi",
    )

    assert (
        hass.states.get("sensor.test_wifi_current_version").state == "softwareVersion"
    )
    assert hass.states.get("sensor.test_wifi_new_version").state == "idle"
    assert hass.states.get("sensor.test_wifi_uptime").state == "1.0"
    assert hass.states.get("sensor.test_wifi_local_ip").state == "10.0.0.10"
    assert hass.states.get("sensor.test_wifi_status").state == "True"


@pytest.mark.usefixtures("mock_success")
async def test_sensor_updates_after_failure_and_recovery(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the sensors become unavailable on failure and recover on the next poll."""
    await setup_sensor_platform(
        hass,
        name="Test Wifi",
    )

    aioclient_mock.clear_requests()
    aioclient_mock.get(RESOURCE_URL, exc=aiohttp.ClientError("boom"))
    await fire_polling_update(hass, 31)
    assert hass.states.get("sensor.test_wifi_uptime").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.test_wifi_status").state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(RESOURCE_URL, json=UPDATED_RESPONSE)
    await fire_polling_update(hass, 62)

    assert hass.states.get("sensor.test_wifi_current_version").state == "newVersion"
    assert hass.states.get("sensor.test_wifi_new_version").state == "latest"
    assert hass.states.get("sensor.test_wifi_uptime").state == "2.0"
    assert hass.states.get("sensor.test_wifi_local_ip").state == "10.0.0.11"
    assert hass.states.get("sensor.test_wifi_status").state == "False"
