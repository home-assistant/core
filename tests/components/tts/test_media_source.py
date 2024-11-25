"""Tests for TTS media source."""

from http import HTTPStatus
import re
from unittest.mock import MagicMock

import pytest

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError
from homeassistant.components.tts.media_source import (
    MediaSourceOptions,
    generate_media_source_id,
    media_source_id_to_kwargs,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    DEFAULT_LANG,
    MockTTSEntity,
    MockTTSProvider,
    mock_config_entry_setup,
    mock_setup,
    retrieve_media,
)

from tests.typing import ClientSessionGenerator


class MSEntity(MockTTSEntity):
    """Test speech API entity."""

    get_tts_audio = MagicMock(return_value=("mp3", b""))


class MSProvider(MockTTSProvider):
    """Test speech API provider."""

    get_tts_audio = MagicMock(return_value=("mp3", b""))


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MSProvider(DEFAULT_LANG), MSEntity(DEFAULT_LANG))],
)
@pytest.mark.parametrize(
    "setup",
    [
        "mock_setup",
        "mock_config_entry_setup",
    ],
    indirect=["setup"],
)
async def test_browsing(hass: HomeAssistant, setup: str) -> None:
    """Test browsing TTS media source."""
    item = await media_source.async_browse_media(hass, "media-source://tts")

    assert item is not None
    assert item.title == "Text-to-speech"
    assert item.children is not None
    assert len(item.children) == 1
    assert item.can_play is False
    assert item.can_expand is True

    item_child = await media_source.async_browse_media(
        hass, item.children[0].media_content_id
    )

    assert item_child is not None
    assert item_child.media_content_id == item.children[0].media_content_id
    assert item_child.title == "Test"
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
    assert item_child.title == "Test"
    assert item_child.children is None
    assert item_child.can_play is False
    assert item_child.can_expand is True

    with pytest.raises(BrowseError):
        await media_source.async_browse_media(hass, "media-source://tts/non-existing")


@pytest.mark.parametrize(
    ("mock_provider", "extra_options"),
    [
        (MSProvider(DEFAULT_LANG), "&tts_options=%7B%22voice%22%3A%22Paulus%22%7D"),
        (MSProvider(DEFAULT_LANG), "&voice=Paulus"),
    ],
)
async def test_legacy_resolving(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_provider: MSProvider,
    extra_options: str,
) -> None:
    """Test resolving legacy provider."""
    await mock_setup(hass, mock_provider)
    mock_get_tts_audio = mock_provider.get_tts_audio

    mock_get_tts_audio.reset_mock()
    media_id = "media-source://tts/test?message=Hello%20World"
    media = await media_source.async_resolve_media(hass, media_id, None)
    assert media.url.startswith("/api/tts_proxy/")
    assert media.mime_type == "audio/mpeg"
    assert await retrieve_media(hass, hass_client, media_id) == HTTPStatus.OK

    assert len(mock_get_tts_audio.mock_calls) == 1
    message, language = mock_get_tts_audio.mock_calls[0][1]
    assert message == "Hello World"
    assert language == "en_US"
    assert mock_get_tts_audio.mock_calls[0][2]["options"] == {}

    # Pass language and options
    mock_get_tts_audio.reset_mock()
    media_id = (
        f"media-source://tts/test?message=Bye%20World&language=de_DE{extra_options}"
    )
    media = await media_source.async_resolve_media(hass, media_id, None)
    assert media.url.startswith("/api/tts_proxy/")
    assert media.mime_type == "audio/mpeg"
    assert await retrieve_media(hass, hass_client, media_id) == HTTPStatus.OK

    assert len(mock_get_tts_audio.mock_calls) == 1
    message, language = mock_get_tts_audio.mock_calls[0][1]
    assert message == "Bye World"
    assert language == "de_DE"
    assert mock_get_tts_audio.mock_calls[0][2]["options"] == {"voice": "Paulus"}


@pytest.mark.parametrize(
    ("mock_tts_entity", "extra_options"),
    [
        (MSEntity(DEFAULT_LANG), "&tts_options=%7B%22voice%22%3A%22Paulus%22%7D"),
        (MSEntity(DEFAULT_LANG), "&voice=Paulus"),
    ],
)
async def test_resolving(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_entity: MSEntity,
    extra_options: str,
) -> None:
    """Test resolving entity."""
    await mock_config_entry_setup(hass, mock_tts_entity)
    mock_get_tts_audio = mock_tts_entity.get_tts_audio

    mock_get_tts_audio.reset_mock()
    media_id = "media-source://tts/tts.test?message=Hello%20World"
    media = await media_source.async_resolve_media(hass, media_id, None)
    assert media.url.startswith("/api/tts_proxy/")
    assert media.mime_type == "audio/mpeg"
    assert await retrieve_media(hass, hass_client, media_id) == HTTPStatus.OK

    assert len(mock_get_tts_audio.mock_calls) == 1
    message, language = mock_get_tts_audio.mock_calls[0][1]
    assert message == "Hello World"
    assert language == "en_US"
    assert mock_get_tts_audio.mock_calls[0][2]["options"] == {}

    # Pass language and options
    mock_get_tts_audio.reset_mock()
    media_id = (
        f"media-source://tts/tts.test?message=Bye%20World&language=de_DE{extra_options}"
    )
    media = await media_source.async_resolve_media(hass, media_id, None)
    assert media.url.startswith("/api/tts_proxy/")
    assert media.mime_type == "audio/mpeg"
    assert await retrieve_media(hass, hass_client, media_id) == HTTPStatus.OK

    assert len(mock_get_tts_audio.mock_calls) == 1
    message, language = mock_get_tts_audio.mock_calls[0][1]
    assert message == "Bye World"
    assert language == "de_DE"
    assert mock_get_tts_audio.mock_calls[0][2]["options"] == {"voice": "Paulus"}


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MSProvider(DEFAULT_LANG), MSEntity(DEFAULT_LANG))],
)
@pytest.mark.parametrize(
    ("setup", "engine"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
async def test_resolving_errors(hass: HomeAssistant, setup: str, engine: str) -> None:
    """Test resolving."""
    # No message added
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(hass, "media-source://tts/test", None)

    # Non-existing provider
    with pytest.raises(
        media_source.Unresolvable, match="Provider non-existing not found"
    ):
        await media_source.async_resolve_media(
            hass, "media-source://tts/non-existing?message=bla", None
        )

    # Non-JSON tts options
    with pytest.raises(
        media_source.Unresolvable,
        match="Invalid TTS options: Expecting property name enclosed in double quotes",
    ):
        await media_source.async_resolve_media(
            hass,
            f"media-source://tts/{engine}?message=bla&tts_options=%7Binvalid json",
            None,
        )

    # Non-existing option
    with pytest.raises(
        media_source.Unresolvable,
        match=re.escape("Invalid options found: ['non_existing_option']"),
    ):
        await media_source.async_resolve_media(
            hass,
            f"media-source://tts/{engine}?message=bla&tts_options=%7B%22non_existing_option%22%3A%22bla%22%7D",
            None,
        )


@pytest.mark.parametrize(
    ("setup", "result_engine"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
async def test_generate_media_source_id_and_media_source_id_to_kwargs(
    hass: HomeAssistant,
    setup: str,
    result_engine: str,
) -> None:
    """Test media_source_id and media_source_id_to_kwargs."""
    kwargs: MediaSourceOptions = {
        "engine": None,
        "message": "hello",
        "language": "en_US",
        "options": {"age": 5},
        "cache": True,
    }
    media_source_id = generate_media_source_id(hass, **kwargs)
    assert media_source_id_to_kwargs(media_source_id) == {
        "engine": result_engine,
        "message": "hello",
        "language": "en_US",
        "options": {"age": 5},
        "cache": True,
    }

    kwargs = {
        "engine": None,
        "message": "hello",
        "language": "en_US",
        "options": {"age": [5, 6]},
        "cache": True,
    }
    media_source_id = generate_media_source_id(hass, **kwargs)
    assert media_source_id_to_kwargs(media_source_id) == {
        "engine": result_engine,
        "message": "hello",
        "language": "en_US",
        "options": {"age": [5, 6]},
        "cache": True,
    }

    kwargs = {
        "engine": None,
        "message": "hello",
        "language": "en_US",
        "options": {"age": {"k1": [5, 6], "k2": "v2"}},
        "cache": True,
    }
    media_source_id = generate_media_source_id(hass, **kwargs)
    assert media_source_id_to_kwargs(media_source_id) == {
        "engine": result_engine,
        "message": "hello",
        "language": "en_US",
        "options": {"age": {"k1": [5, 6], "k2": "v2"}},
        "cache": True,
    }
