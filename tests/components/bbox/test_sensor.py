"""Tests for the Bbox sensor platform."""

from datetime import timedelta

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.bbox.api import BboxConnectionError
from homeassistant.components.bbox.const import DEFAULT_HOST
from homeassistant.components.bbox.sensor import PLATFORM_SCHEMA, BboxData
from homeassistant.const import CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import (
    DEVICE_INFO_RESPONSE,
    DEVICE_URL,
    HOST,
    UPTIME,
    WAN_IP_STATS_RESPONSE,
    WAN_IP_STATS_URL,
)

SENSOR_PLATFORM_CONFIG = {
    "platform": "bbox",
    "monitored_variables": [
        "down_max_bandwidth",
        "up_max_bandwidth",
        "current_down_bandwidth",
        "current_up_bandwidth",
        "number_of_reboots",
        "uptime",
    ],
}

EXPECTED_STATES = {
    "sensor.bbox_maximum_download_bandwidth": "1000.0",
    "sensor.bbox_maximum_upload_bandwidth": "1000.0",
    "sensor.bbox_currently_used_download_bandwidth": "17.95",
    "sensor.bbox_currently_used_upload_bandwidth": "3.46",
    "sensor.bbox_number_of_reboot": "40",
}


@pytest.fixture
def mock_bbox(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Register the standard Bbox answers for the sensor endpoints."""
    aioclient_mock.get(WAN_IP_STATS_URL, json=WAN_IP_STATS_RESPONSE)
    aioclient_mock.get(DEVICE_URL, json=DEVICE_INFO_RESPONSE)
    return aioclient_mock


def test_platform_schema_defaults() -> None:
    """Test the sensor platform defaults for host and verify_ssl."""
    config = PLATFORM_SCHEMA({**SENSOR_PLATFORM_CONFIG})
    assert config[CONF_HOST] == DEFAULT_HOST
    assert config[CONF_VERIFY_SSL] is True
    config = PLATFORM_SCHEMA({**SENSOR_PLATFORM_CONFIG, "verify_ssl": False})
    assert config[CONF_VERIFY_SSL] is False


async def test_sensors(
    hass: HomeAssistant,
    mock_bbox: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the platform exposes the WAN stats and device info."""
    freezer.move_to("2026-11-11T15:00:00+00:00")
    assert await async_setup_component(
        hass, "sensor", {"sensor": SENSOR_PLATFORM_CONFIG}
    )
    await hass.async_block_till_done()

    expected_uptime = (utcnow() - timedelta(seconds=UPTIME)).isoformat()
    for entity_id, state in EXPECTED_STATES.items():
        assert hass.states.get(entity_id).state == state, entity_id
    assert hass.states.get("sensor.bbox_uptime").state == expected_uptime


async def test_setup_platform_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that no entities are exposed when the Bbox is unreachable."""
    aioclient_mock.get(WAN_IP_STATS_URL, exc=ClientConnectionError("boom"))
    aioclient_mock.get(DEVICE_URL, exc=ClientConnectionError("boom"))
    assert await async_setup_component(
        hass, "sensor", {"sensor": SENSOR_PLATFORM_CONFIG}
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.bbox_uptime") is None


async def test_bbox_data_is_throttled(
    hass: HomeAssistant,
    mock_bbox: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the first update is repeated only after the throttle."""
    freezer.move_to("2026-11-11T15:00:00+00:00")
    bbox_data = BboxData(hass, HOST, "")
    await hass.async_add_executor_job(bbox_data.update)
    assert bbox_data.data == WAN_IP_STATS_RESPONSE[0]["wan"]["ip"]["stats"]
    assert bbox_data.router_infos == DEVICE_INFO_RESPONSE[0]
    assert mock_bbox.call_count == 2

    await hass.async_add_executor_job(bbox_data.update)
    assert mock_bbox.call_count == 2

    freezer.tick(timedelta(seconds=61))
    await hass.async_add_executor_job(bbox_data.update)
    assert mock_bbox.call_count == 4


async def test_update_raises_and_keeps_last_value_on_failure(
    hass: HomeAssistant,
    mock_bbox: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a failed refresh raises and keeps the last known payloads."""
    freezer.move_to("2026-11-11T15:00:00+00:00")
    bbox_data = BboxData(hass, HOST, "")
    await hass.async_add_executor_job(bbox_data.update)
    assert bbox_data.data is not None

    mock_bbox.clear_requests()
    mock_bbox.get(WAN_IP_STATS_URL, exc=ClientConnectionError("boom"))
    mock_bbox.get(DEVICE_URL, exc=ClientConnectionError("boom"))
    freezer.tick(timedelta(seconds=61))
    with pytest.raises(BboxConnectionError):
        await hass.async_add_executor_job(bbox_data.update)
    # The last known payloads are kept, not cleared.
    assert bbox_data.data == WAN_IP_STATS_RESPONSE[0]["wan"]["ip"]["stats"]
    assert bbox_data.router_infos == DEVICE_INFO_RESPONSE[0]
