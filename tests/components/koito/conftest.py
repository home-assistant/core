"""Common fixtures for the Koito integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiokoito import KoitoData, MusicItem, NowPlaying, RankedItem, SimpleArtist, Summary
import pytest

from homeassistant.components.koito.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL

from tests.common import MockConfigEntry

SUMMARY = Summary(
    plays=42,
    minutes_listened=120,
    unique_tracks=9,
    unique_albums=4,
    unique_artists=3,
    top_artists=(
        RankedItem(
            rank=1,
            item=MusicItem(name="Artist", image="https://koito.example/artist.webp"),
        ),
    ),
    top_albums=(
        RankedItem(
            rank=1,
            item=MusicItem(
                title="Album",
                artists=(SimpleArtist(name="Artist"),),
                image="https://koito.example/album.webp",
            ),
        ),
    ),
    top_tracks=(
        RankedItem(
            rank=1,
            item=MusicItem(
                title="Song",
                artists=(SimpleArtist(name="Artist"),),
                image="https://koito.example/song.webp",
            ),
        ),
    ),
)
DATA = KoitoData(
    summary=SUMMARY,
    now_playing=NowPlaying(
        currently_playing=True,
        track=MusicItem(
            title="Song",
            artists=(SimpleArtist(name="Artist"),),
            image="https://koito.example/song.webp",
        ),
    ),
)


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the published API client at the integration boundary."""
    with (
        patch("homeassistant.components.koito.KoitoApi", autospec=True) as client,
        patch("homeassistant.components.koito.config_flow.KoitoApi", new=client),
    ):
        client.return_value.async_get_summary.return_value = SUMMARY
        client.return_value.base_url = "https://koito.example"
        client.return_value.async_fetch_data.return_value = DATA
        yield client.return_value


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Keep flow tests focused on configuration."""
    with patch(
        "homeassistant.components.koito.async_setup_entry", return_value=True
    ) as setup:
        yield setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a deterministic entry for entity snapshots."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01J000000000000000000000000",
        title="Koito",
        data={CONF_URL: "https://koito.example", CONF_API_KEY: "old-key"},
    )
