"""Tests for TTS media source."""

import asyncio
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import media_source
from homeassistant.components.media_player import BrowseError
from homeassistant.components.tts import TtsAudioType
from homeassistant.components.tts.media_source import (
    generate_media_source_id,
    parse_media_source_id,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    DEFAULT_LANG,
    MockResultStream,
    MockTTSEntity,
    MockTTSProvider,
    mock_config_entry_setup,
    mock_setup,
    retrieve_media,
)


class MSEntity(MockTTSEntity):
    """Test speech API entity."""

    get_tts_audio = MagicMock(return_value=("mp3", b""))


class SlowMSEntity(MockTTSEntity):
    """Test speech API entity that waits before returning audio."""

    def __init__(self, lang: str) -> None:
        """Initialize entity."""
        super().__init__(lang)
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Return audio once released."""
        self.started.set()
        await self.release.wait()
        return ("mp3", b"slow audio")


class FailingMSEntity(MockTTSEntity):
    """Test speech API entity that fails to generate audio."""

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Fail to generate audio."""
        raise RuntimeError("Boom!")


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
    assert item_child.thumbnail == "/api/brands/integration/test/logo.png"

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

    mock_provider.has_entity = True
    root = await media_source.async_browse_media(hass, "media-source://tts")
    assert len(root.children) == 0
    mock_provider.has_entity = False
    root = await media_source.async_browse_media(hass, "media-source://tts")
    assert len(root.children) == 1

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

    # Test with result stream
    stream = MockResultStream(hass, "wav", b"")
    media = await media_source.async_resolve_media(hass, stream.media_source_id, None)
    assert media.url == stream.url
    assert media.mime_type == stream.content_type
    assert media.path is None

    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(
            hass, "media-source://tts/-stream-/not-a-valid-token", None
        )


@pytest.mark.parametrize(
    "mock_tts_entity",
    [MSEntity(DEFAULT_LANG)],
)
async def test_resolving_sets_path_when_cached_on_disk(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_cache_dir: Path,
    mock_tts_entity: MSEntity,
) -> None:
    """Test resolving exposes the on-disk file path once cached."""
    await mock_config_entry_setup(hass, mock_tts_entity)

    media_id = "media-source://tts/tts.test?message=Hello%20World&cache=true"

    # Generate and persist the file to disk.
    assert await retrieve_media(hass, hass_client, media_id) == HTTPStatus.OK
    await hass.async_block_till_done(wait_background_tasks=True)

    # Resolving now exposes the cached file on disk.
    media = await media_source.async_resolve_media(hass, media_id, None)
    assert media.url.startswith("/api/tts_proxy/")
    assert media.path is not None
    assert media.path.parent == mock_tts_cache_dir
    assert media.path.is_file()


@pytest.mark.parametrize(
    "mock_tts_entity",
    [MSEntity(DEFAULT_LANG)],
)
async def test_resolving_no_path_without_file_cache(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_cache_dir: Path,
    mock_tts_entity: MSEntity,
) -> None:
    """Test resolving does not expose a path when file caching is disabled."""
    await mock_config_entry_setup(hass, mock_tts_entity)

    media_id = "media-source://tts/tts.test?message=Hello%20World&cache=false"

    assert await retrieve_media(hass, hass_client, media_id) == HTTPStatus.OK
    await hass.async_block_till_done(wait_background_tasks=True)

    media = await media_source.async_resolve_media(hass, media_id, None)
    assert media.path is None


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
        match="Unsupported options: non_existing_option",
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
async def test_generate_media_source_id_and_parse_media_source_id(
    hass: HomeAssistant,
    setup: str,
    result_engine: str,
) -> None:
    """Test media_source_id and parse_media_source_id."""
    kwargs = {
        "engine": None,
        "message": "hello",
        "language": "en_US",
        "options": {"age": 5},
        "cache": True,
    }
    media_source_id = generate_media_source_id(hass, **kwargs)
    assert parse_media_source_id(media_source_id) == {
        "message": "hello",
        "options": {
            "engine": result_engine,
            "language": "en_US",
            "options": {"age": 5},
            "use_file_cache": True,
        },
        "pregenerate": False,
    }

    kwargs = {
        "engine": None,
        "message": "hello",
        "language": "en_US",
        "options": {"age": [5, 6]},
        "cache": True,
    }
    media_source_id = generate_media_source_id(hass, **kwargs)
    assert parse_media_source_id(media_source_id) == {
        "message": "hello",
        "options": {
            "engine": result_engine,
            "language": "en_US",
            "options": {"age": [5, 6]},
            "use_file_cache": True,
        },
        "pregenerate": False,
    }

    kwargs = {
        "engine": None,
        "message": "hello",
        "language": "en_US",
        "options": {"age": {"k1": [5, 6], "k2": "v2"}},
        "cache": True,
    }
    media_source_id = generate_media_source_id(hass, **kwargs)
    assert parse_media_source_id(media_source_id) == {
        "message": "hello",
        "options": {
            "engine": result_engine,
            "language": "en_US",
            "options": {"age": {"k1": [5, 6], "k2": "v2"}},
            "use_file_cache": True,
        },
        "pregenerate": False,
    }


@pytest.mark.parametrize(
    ("setup", "result_engine"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
async def test_generate_media_source_id_and_parse_pregenerate(
    hass: HomeAssistant,
    setup: str,
    result_engine: str,
) -> None:
    """Test pregenerate round trips through the media source ID."""
    media_source_id = generate_media_source_id(
        hass, message="hello", language="en_US", pregenerate=True
    )
    assert "pregenerate=true" in media_source_id
    assert parse_media_source_id(media_source_id) == {
        "message": "hello",
        "options": {
            "engine": result_engine,
            "language": "en_US",
            "options": None,
            "use_file_cache": None,
        },
        "pregenerate": True,
    }


@pytest.mark.parametrize(
    ("cache", "expected_files"),
    [
        pytest.param("false", 0, id="memory_only"),
        pytest.param("true", 1, id="file_cache"),
    ],
)
async def test_resolving_pregenerate(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_cache_dir: Path,
    cache: str,
    expected_files: int,
) -> None:
    """Test resolving waits until the audio has been fully generated."""
    entity = SlowMSEntity(DEFAULT_LANG)
    await mock_config_entry_setup(hass, entity)

    media_id = (
        "media-source://tts/tts.test?message=Hello%20World"
        f"&cache={cache}&pregenerate=true"
    )
    resolve_task = hass.async_create_task(
        media_source.async_resolve_media(hass, media_id, None)
    )
    await entity.started.wait()
    # The media URL is only handed out once the audio is complete.
    assert not resolve_task.done()

    entity.release.set()
    media = await resolve_task
    assert media.url.startswith("/api/tts_proxy/")

    client = await hass_client()
    response = await client.get(media.url)
    assert response.status == HTTPStatus.OK
    assert await response.read() == b"slow audio"

    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(list(mock_tts_cache_dir.iterdir())) == expected_files


async def test_resolving_pregenerate_error(hass: HomeAssistant) -> None:
    """Test resolving fails when the audio cannot be pregenerated."""
    await mock_config_entry_setup(hass, FailingMSEntity(DEFAULT_LANG))

    with pytest.raises(media_source.Unresolvable, match="Boom!"):
        await media_source.async_resolve_media(
            hass,
            "media-source://tts/tts.test?message=Hello%20World&pregenerate=true",
            None,
        )
