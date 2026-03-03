"""Tests for the WebDAV sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiowebdav2.exceptions import (
    ConnectionExceptionError,
    MethodNotSupportedError,
    UnauthorizedError,
)
from aiowebdav2.models import QuotaInfo
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebDAV sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "sensor",
    [
        "sensor.user_webdav_demo_free_space",
        "sensor.user_webdav_demo_used_space",
    ],
)
async def test_sensor_quota_not_supported(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    sensor: str,
) -> None:
    """Test that sensors are not created when quota is not supported."""
    webdav_client.quota.side_effect = MethodNotSupportedError(
        name="quota", server="https://webdav.demo"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(sensor)
    assert state is None


@pytest.mark.parametrize(
    "sensor",
    [
        "sensor.user_webdav_demo_free_space",
        "sensor.user_webdav_demo_used_space",
    ],
)
async def test_sensor_quota_none_values(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    sensor: str,
) -> None:
    """Test missing sensors when quota returns None values."""
    webdav_client.quota.return_value = QuotaInfo(available_bytes=None, used_bytes=None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(sensor)
    assert state is None


@pytest.mark.parametrize(
    "error",
    [
        UnauthorizedError(
            path="/",
        ),
        ConnectionExceptionError("Connection failed"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_sensor_update_fail(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Test sensors become unavailable and recover after update failure."""
    webdav_client.quota.side_effect = error

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensors should be unavailable
    assert (
        hass.states.get("sensor.user_webdav_demo_free_space").state == STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.user_webdav_demo_used_space").state == STATE_UNAVAILABLE
    )

    webdav_client.quota.side_effect = None
    webdav_client.quota.return_value = QuotaInfo(available_bytes=1000, used_bytes=500)

    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensors should be available again
    assert (
        hass.states.get("sensor.user_webdav_demo_free_space").state != STATE_UNAVAILABLE
    )
    assert (
        hass.states.get("sensor.user_webdav_demo_used_space").state != STATE_UNAVAILABLE
    )
