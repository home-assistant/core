"""Tests for TTS media source."""
from unittest.mock import patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def mock_get_tts_audio(hass):
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})
    assert await async_setup_component(
        hass,
        "tts",
        {
            "tts": {
                "platform": "demo",
            }
        },
    )

    with patch(
        "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
        return_value=("mp3", b""),
    ) as mock_get_tts:
        yield mock_get_tts


async def test_browsing(hass):
    """Test browsing TTS media source."""
    item = await media_source.async_browse_media(hass, "media-source://tts")
    assert item is not None
    assert item.title == "Text to Speech"
    assert len(item.children) == 1
    assert item.can_play is False
    assert item.can_expand is True

    item_child = await media_source.async_browse_media(
        hass, item.children[0].media_content_id
    )
    assert item_child is not None
    assert item_child.media_content_id == item.children[0].media_content_id
    assert item_child.title == "Demo"
    assert item_child.children is None
    assert item_child.can_play is False
    assert item_child.can_expand is True

    item_child = await media_source.async_browse_media(
        hass, item.children[0].media_content_id + "?message=bla"
    )
    assert item_child is not None
    assert (
        item_child.media_content_id
        == item.children[0].media_content_id + "?message=bla"
    )
    assert item_child.title == "Demo"
    assert item_child.children is None
    assert item_child.can_play is False
    assert item_child.can_expand is True

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(hass, "media-source://tts/non-existing")


async def test_resolving(hass, mock_get_tts_audio):
    """Test resolving."""
    media = await media_source.async_resolve_media(
        hass, "media-source://tts/demo?message=Hello%20World", None
    )
    assert media.url.startswith("/api/tts_proxy/")
    assert media.mime_type == "audio/mpeg"

    assert len(mock_get_tts_audio.mock_calls) == 1
    message, language = mock_get_tts_audio.mock_calls[0][1]
    assert message == "Hello World"
    assert language == "en"
    assert mock_get_tts_audio.mock_calls[0][2]["options"] is None

    # Pass language and options
    mock_get_tts_audio.reset_mock()
    media = await media_source.async_resolve_media(
        hass,
        "media-source://tts/demo?message=Bye%20World&language=de&voice=Paulus",
        None,
    )
    assert media.url.startswith("/api/tts_proxy/")
    assert media.mime_type == "audio/mpeg"

    assert len(mock_get_tts_audio.mock_calls) == 1
    message, language = mock_get_tts_audio.mock_calls[0][1]
    assert message == "Bye World"
    assert language == "de"
    assert mock_get_tts_audio.mock_calls[0][2]["options"] == {"voice": "Paulus"}


async def test_resolving_errors(hass):
    """Test resolving."""
    # No message added
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, "media-source://tts/demo", None)

    # Non-existing provider
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(
            hass, "media-source://tts/non-existing?message=bla", None
        )

    # Non-existing option
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(
            hass,
            "media-source://tts/non-existing?message=bla&non_existing_option=bla",
            None,
        )
