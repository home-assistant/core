"""Test the media browser interface."""

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.spotify import DOMAIN
from homeassistant.components.spotify.browse_media import async_browse_media
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_browse_media_root(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    spotify_setup,
) -> None:
    """Test browsing the root."""
    response = await async_browse_media(hass, None, None)
    assert response.as_dict() == snapshot


async def test_browse_media_categories(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    spotify_setup,
) -> None:
    """Test browsing categories."""
    response = await async_browse_media(
        hass, "spotify://library", "spotify://01J5TX5A0FF6G5V0QJX6HBC94T"
    )
    assert response.as_dict() == snapshot


@pytest.mark.parametrize(
    ("config_entry_id"), [("01J5TX5A0FF6G5V0QJX6HBC94T"), ("32oesphrnacjcf7vw5bf6odx3")]
)
async def test_browse_media_playlists(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry_id: str,
    spotify_setup,
) -> None:
    """Test browsing playlists for the two config entries."""
    response = await async_browse_media(
        hass,
        "spotify://current_user_playlists",
        f"spotify://{config_entry_id}/current_user_playlists",
    )
    assert response.as_dict() == snapshot
