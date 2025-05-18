"""Test the Immich sensor platform."""

from unittest.mock import Mock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Immich sensor platform."""

    with patch("homeassistant.components.immich.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_admin_sensors(
    hass: HomeAssistant,
    mock_non_admin_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the integration doesn't create admin sensors if not admin."""

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.mock_title_photos_count") is None
    assert hass.states.get("sensor.mock_title_videos_count") is None
    assert hass.states.get("sensor.mock_title_disk_used_by_photos") is None
    assert hass.states.get("sensor.mock_title_disk_used_by_videos") is None
