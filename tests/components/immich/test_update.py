"""Test the Immich update platform."""

from unittest.mock import Mock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Immich update platform."""

    with patch("homeassistant.components.immich.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_update_min_version(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_immich: Mock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Immich update platform with min version not installed."""

    mock_immich.server.async_get_about_info.return_value.version = "v1.132.3"

    with patch("homeassistant.components.immich.PLATFORMS", [Platform.UPDATE]):
        await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_all()
