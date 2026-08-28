"""Test Discogs sensor platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.discogs.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Test sensor states."""
    state = hass.states.get("sensor.discogs_collection")
    assert state is not None
    assert state.state == "42"
    assert state.attributes["identity"] == "testuser"

    state = hass.states.get("sensor.discogs_wantlist")
    assert state is not None
    assert state.state == "10"
    assert state.attributes["identity"] == "testuser"

    state = hass.states.get("sensor.discogs_random_record")
    assert state is not None
    assert state.state == "Artist Name - Album Title"
    assert state.attributes["identity"] == "testuser"
    assert state.attributes["cat_no"] == "CAT001"
    assert state.attributes["cover_image"] == "https://example.com/cover.jpg"
    assert state.attributes["format"] == "Vinyl (LP)"
    assert state.attributes["label"] == "Label Name"
    assert state.attributes["released"] == "2023"


async def test_sensors_empty_collection(hass: HomeAssistant) -> None:
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

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="testuser",
        data={"token": "test_token"},
        unique_id="testuser",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.discogs.coordinator.discogs_client.Client",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.discogs_collection")
    assert state is not None
    assert state.state == "0"

    state = hass.states.get("sensor.discogs_wantlist")
    assert state is not None
    assert state.state == "0"

    state = hass.states.get("sensor.discogs_random_record")
    assert state is not None
    assert state.state == "unknown"
