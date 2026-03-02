"""Tests for the WebDAV sensor platform."""

from unittest.mock import AsyncMock

from aiowebdav2.exceptions import MethodNotSupportedError
from aiowebdav2.models import QuotaInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test WebDAV sensors."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_quota_not_supported(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors are not created when quota is not supported."""
    webdav_client.quota.side_effect = MethodNotSupportedError(
        name="quota", server="https://webdav.demo"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    # No sensor entities should be created
    assert len(entity_entries) == 0


async def test_sensor_quota_none_values(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing sensors when quota returns None values."""
    webdav_client.quota.return_value = QuotaInfo(available_bytes=None, used_bytes=None)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.webdav_free_space")
    assert state is None

    state = hass.states.get("sensor.webdav_used_space")
    assert state is None
