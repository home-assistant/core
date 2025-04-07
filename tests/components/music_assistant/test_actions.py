"""Test Music Assistant actions."""

from unittest.mock import AsyncMock, MagicMock

from music_assistant_models.media_items import SearchResults
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.music_assistant.actions import (
    SERVICE_GET_LIBRARY,
    SERVICE_SEARCH,
)
from homeassistant.components.music_assistant.const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_FAVORITE,
    ATTR_MEDIA_TYPE,
    ATTR_SEARCH_NAME,
    DOMAIN as MASS_DOMAIN,
)
from homeassistant.core import HomeAssistant

from .common import create_library_albums_from_fixture, setup_integration_from_fixtures


async def test_search_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test music assistant search action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)

    music_assistant_client.music.search = AsyncMock(
        return_value=SearchResults(
            albums=create_library_albums_from_fixture(),
        )
    )
    response = await hass.services.async_call(
        MASS_DOMAIN,
        SERVICE_SEARCH,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_SEARCH_NAME: "test",
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    "media_type",
    [
        "artist",
        "album",
        "track",
        "playlist",
        "audiobook",
        "podcast",
        "radio",
    ],
)
async def test_get_library_action(
    hass: HomeAssistant,
    music_assistant_client: MagicMock,
    media_type: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test music assistant get_library action."""
    entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    response = await hass.services.async_call(
        MASS_DOMAIN,
        SERVICE_GET_LIBRARY,
        {
            ATTR_CONFIG_ENTRY_ID: entry.entry_id,
            ATTR_FAVORITE: False,
            ATTR_MEDIA_TYPE: media_type,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot
