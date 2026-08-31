"""Configure tests for the Discogs integration."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.discogs.const import DOMAIN
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_TOKEN, MOCK_USER_ID, MOCK_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock Discogs config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={CONF_TOKEN: MOCK_TOKEN},
        unique_id=str(MOCK_USER_ID),
    )


@pytest.fixture
def mock_discogs_data() -> dict:
    """Return mock Discogs data for a random record."""
    return {
        "artists": [{"name": "Artist Name"}],
        "title": "Album Title",
        "labels": [{"catno": "CAT001", "name": "Label Name"}],
        "cover_image": "https://example.com/cover.jpg",
        "formats": [{"name": "Vinyl", "descriptions": ["LP", "Album"]}],
        "year": "2023",
    }


@pytest.fixture
def mock_identity(mock_discogs_data: dict) -> MagicMock:
    """Return a mock Discogs identity."""
    identity = MagicMock()
    identity.id = MOCK_USER_ID
    identity.name = MOCK_USERNAME
    identity.num_collection = 42
    identity.num_wantlist = 10

    release = MagicMock()
    release.release.data = mock_discogs_data

    folder = MagicMock()
    folder.count = 42
    folder.releases.__getitem__ = MagicMock(return_value=release)

    identity.collection_folders = [folder]
    return identity


@pytest.fixture
def mock_client(mock_identity: MagicMock) -> MagicMock:
    """Return a mock Discogs client."""
    client = MagicMock()
    client.identity.return_value = mock_identity
    return client


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Discogs integration for testing."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.discogs.sensor.discogs_client.Client",
        return_value=mock_client,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    return config_entry
