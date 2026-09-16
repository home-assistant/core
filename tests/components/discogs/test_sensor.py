"""Test Discogs sensor platform."""

from unittest.mock import MagicMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_discogs_client: MagicMock,
) -> None:
    """Test sensor entities with snapshot."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.discogs.PLATFORMS", [Platform.SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensors_empty_collection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensors when the collection is empty."""
    mock_identity = MagicMock()
    mock_identity.name = "testuser"
    mock_identity.num_collection = 0
    mock_identity.num_wantlist = 0

    folder = MagicMock()
    folder.count = 0
    mock_identity.collection_folders = [folder]

    mock_client = MagicMock()
    mock_client.identity.return_value = mock_identity

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.discogs.discogs_client.Client",
            return_value=mock_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.testuser_collection")
    assert state is not None
    assert state.state == "0"

    state = hass.states.get("sensor.testuser_wantlist")
    assert state is not None
    assert state.state == "0"

    state = hass.states.get("sensor.testuser_random_record")
    assert state is not None
    assert state.state == "unknown"
