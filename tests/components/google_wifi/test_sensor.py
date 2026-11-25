"""The tests for the Google Wifi sensor platform."""

from datetime import timedelta
from typing import Any

import aiohttp
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    assert_setup_component,
    async_fire_time_changed,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.google_wifi import const
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import LEAF_RESPONSE, RESOURCE_URL, SPEAKER_RESPONSE, UPDATED_RESPONSE

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
async def test_config_entry_setup_links_entities_to_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test config-entry setup creates and links entities to the router device."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entry = entity_registry.async_get("sensor.google_wifi_uptime")
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.device_id is not None

    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert (const.DOMAIN, "GALE [REDACTED]") in device_entry.identifiers


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
    """Test YAML setup aborts when the router does not respond."""
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
    assert hass.states.get("sensor.google_wifi_uptime") is None


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
    assert hass.states.get("sensor.test_wifi_new_version").state == "Latest"
    assert hass.states.get("sensor.test_wifi_uptime").state == "1.0"
    assert hass.states.get("sensor.test_wifi_local_ip").state == "10.0.0.10"
    assert hass.states.get("sensor.test_wifi_status").state == "Online"


@pytest.mark.parametrize(
    ("device_response", "expected_status", "expected_local_ip"),
    [
        pytest.param(LEAF_RESPONSE, "Online", "192.168.86.21", id="mesh-point"),
        pytest.param(SPEAKER_RESPONSE, "Offline", None, id="speaker"),
    ],
    indirect=["device_response"],
)
@pytest.mark.usefixtures("mock_device_response")
async def test_sensor_states_for_limited_device_data(
    hass: HomeAssistant,
    expected_status: str,
    expected_local_ip: str | None,
) -> None:
    """Test sensor states with leaf and speaker responses."""
    await setup_sensor_platform(hass, name="Test Wifi")

    status = hass.states.get("sensor.test_wifi_status")
    local_ip = hass.states.get("sensor.test_wifi_local_ip")
    assert status is not None
    assert status.state == expected_status
    if expected_local_ip:
        assert local_ip is not None
        assert local_ip.state == expected_local_ip


@pytest.mark.parametrize(
    "monitored_conditions",
    [
        [const.ATTR_UPTIME],
        [const.ATTR_CURRENT_VERSION, const.ATTR_STATUS],
        [const.ATTR_LOCAL_IP],
    ],
)
@pytest.mark.usefixtures("mock_success")
async def test_setup_with_limited_monitored_conditions(
    hass: HomeAssistant,
    monitored_conditions: list[str],
) -> None:
    """Test setup creates only explicitly monitored sensors."""
    await setup_sensor_platform(
        hass,
        name="Test Wifi",
        monitored_conditions=monitored_conditions,
    )

    assert_setup_component(len(monitored_conditions), "sensor")


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
    aioclient_mock.get(
        RESOURCE_URL,
        exc=aiohttp.ClientConnectionError("connection refused"),
    )
    await fire_polling_update(hass, 31)
    assert hass.states.get("sensor.test_wifi_uptime").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.test_wifi_status").state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(RESOURCE_URL, json=UPDATED_RESPONSE)
    await fire_polling_update(hass, 62)

    assert hass.states.get("sensor.test_wifi_current_version").state == "newVersion"
    assert hass.states.get("sensor.test_wifi_new_version").state == "1.2.3.4"
    assert hass.states.get("sensor.test_wifi_uptime").state == "2.0"
    assert hass.states.get("sensor.test_wifi_local_ip").state == STATE_UNKNOWN
    assert hass.states.get("sensor.test_wifi_status").state == "Offline"
