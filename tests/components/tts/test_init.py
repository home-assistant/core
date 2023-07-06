"""The tests for the TTS component."""
import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.components.media_source import Unresolvable
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import (
    DEFAULT_LANG,
    SUPPORT_LANGUAGES,
    TEST_DOMAIN,
    MockProvider,
    MockTTSEntity,
    get_media_source_url,
    mock_config_entry_setup,
    mock_setup,
)

from tests.common import async_mock_service, mock_restore_cache
from tests.typing import ClientSessionGenerator, WebSocketGenerator

ORIG_WRITE_TAGS = tts.SpeechManager.write_tags


@pytest.fixture
async def setup_tts(hass: HomeAssistant, mock_tts: None) -> None:
    """Mock TTS."""
    assert await async_setup_component(hass, tts.DOMAIN, {"tts": {"platform": "test"}})


class DefaultEntity(tts.TextToSpeechEntity):
    """Test entity."""

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return DEFAULT_LANG


async def test_default_entity_attributes() -> None:
    """Test default entity attributes."""
    entity = DefaultEntity()

    assert entity.hass is None
    assert entity.name is UNDEFINED
    assert entity.default_language == DEFAULT_LANG
    assert entity.supported_languages == SUPPORT_LANGUAGES
    assert entity.supported_options is None
    assert entity.default_options is None
    assert entity.async_get_supported_voices("test") is None


async def test_config_entry_unload(
    hass: HomeAssistant, mock_tts_entity: MockTTSEntity
) -> None:
    """Test we can unload config entry."""
    entity_id = f"{tts.DOMAIN}.{TEST_DOMAIN}"
    state = hass.states.get(entity_id)
    assert state is None

    config_entry = await mock_config_entry_setup(hass, mock_tts_entity)
    assert config_entry.state == ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    now = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        await hass.services.async_call(
            tts.DOMAIN,
            "speak",
            {
                ATTR_ENTITY_ID: entity_id,
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            blocking=True,
        )
        assert len(calls) == 1

        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == now.isoformat()

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED

    state = hass.states.get(entity_id)
    assert state is None


async def test_restore_state(
    hass: HomeAssistant,
    mock_tts_entity: MockTTSEntity,
) -> None:
    """Test we restore state in the integration."""
    entity_id = f"{tts.DOMAIN}.{TEST_DOMAIN}"
    timestamp = "2023-01-01T23:59:59+00:00"
    mock_restore_cache(hass, (State(entity_id, timestamp),))

    config_entry = await mock_config_entry_setup(hass, mock_tts_entity)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state
    assert state.state == timestamp


@pytest.mark.parametrize(
    "setup", ["mock_setup", "mock_config_entry_setup"], indirect=True
)
async def test_setup_component(hass: HomeAssistant, setup: str) -> None:
    """Set up a TTS platform with defaults."""
    assert hass.services.has_service(tts.DOMAIN, "clear_cache")
    assert f"{tts.DOMAIN}.test" in hass.config.components


@pytest.mark.parametrize("init_tts_cache_dir_side_effect", [OSError(2, "No access")])
@pytest.mark.parametrize(
    "setup", ["mock_setup", "mock_config_entry_setup"], indirect=True
)
async def test_setup_component_no_access_cache_folder(
    hass: HomeAssistant, mock_tts_init_cache_dir: MagicMock, setup: str
) -> None:
    """Set up a TTS platform with defaults."""
    assert not hass.services.has_service(tts.DOMAIN, "test_say")
    assert not hass.services.has_service(tts.DOMAIN, "clear_cache")


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_ANNOUNCE] is True
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_en-us_-_{expected_url_suffix}.mp3"
    )
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_{expected_url_suffix}.mp3"
    ).is_file()


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MockProvider("de_DE"), MockTTSEntity("de_DE"))],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_default_language(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform with default language and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_de-de_-_{expected_url_suffix}.mp3"
    )
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / (
            f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de-de_-_{expected_url_suffix}.mp3"
        )
    ).is_file()


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MockProvider("en_US"), MockTTSEntity("en_US"))],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_default_special_language(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform with default special language and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_en-us_-_{expected_url_suffix}.mp3"
    )
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_{expected_url_suffix}.mp3"
    ).is_file()


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_language(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service with language."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_de-de_-_{expected_url_suffix}.mp3"
    )
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de-de_-_{expected_url_suffix}.mp3"
    ).is_file()


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "lang",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "lang",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_wrong_language(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            tts.DOMAIN,
            tts_service,
            service_data,
            blocking=True,
        )
    assert len(calls) == 0
    assert not (
        mock_tts_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_lang_-_{expected_url_suffix}.mp3"
    ).is_file()


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
                tts.ATTR_OPTIONS: {"voice": "alex", "age": 5},
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
                tts.ATTR_OPTIONS: {"voice": "alex", "age": 5},
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_options(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service with options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    opt_hash = tts._hash_options({"voice": "alex", "age": 5})

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_de-de_{opt_hash}_{expected_url_suffix}.mp3"
    )
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / (
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_de-de_{opt_hash}_{expected_url_suffix}.mp3"
        )
    ).is_file()


class MockProviderWithDefaults(MockProvider):
    """Mock provider with default options."""

    @property
    def default_options(self):
        """Return a mapping with the default options."""
        return {"voice": "alex"}


class MockEntityWithDefaults(MockTTSEntity):
    """Mock entity with default options."""

    @property
    def default_options(self):
        """Return a mapping with the default options."""
        return {"voice": "alex"}


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MockProviderWithDefaults(DEFAULT_LANG), MockEntityWithDefaults(DEFAULT_LANG))],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_default_options(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service with default options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    opt_hash = tts._hash_options({"voice": "alex"})

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_de-de_{opt_hash}_{expected_url_suffix}.mp3"
    )
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / (
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_de-de_{opt_hash}_{expected_url_suffix}.mp3"
        )
    ).is_file()


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MockProviderWithDefaults(DEFAULT_LANG), MockEntityWithDefaults(DEFAULT_LANG))],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
                tts.ATTR_OPTIONS: {"age": 5},
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
                tts.ATTR_OPTIONS: {"age": 5},
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_merge_default_service_options(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service with default options.

    This tests merging default and user provided options.
    """
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    opt_hash = tts._hash_options({"voice": "alex", "age": 5})

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_de-de_{opt_hash}_{expected_url_suffix}.mp3"
    )
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / (
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_de-de_{opt_hash}_{expected_url_suffix}.mp3"
        )
    ).is_file()


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
                tts.ATTR_OPTIONS: {"speed": 1},
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de_DE",
                tts.ATTR_OPTIONS: {"speed": 1},
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_wrong_options(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service with wrong options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            tts.DOMAIN,
            tts_service,
            service_data,
            blocking=True,
        )
    opt_hash = tts._hash_options({"speed": 1})

    assert len(calls) == 0
    await hass.async_block_till_done()
    assert not (
        mock_tts_cache_dir
        / (
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_de-de_{opt_hash}_{expected_url_suffix}.mp3"
        )
    ).is_file()


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_clear_cache(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service clear cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    # To make sure the file is persisted
    assert len(calls) == 1
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    await hass.async_block_till_done()
    assert (
        mock_tts_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_{expected_url_suffix}.mp3"
    ).is_file()

    await hass.services.async_call(
        tts.DOMAIN, tts.SERVICE_CLEAR_CACHE, {}, blocking=True
    )

    assert not (
        mock_tts_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_{expected_url_suffix}.mp3"
    ).is_file()


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_receive_voice(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service and receive voice."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    assert len(calls) == 1

    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    await hass.async_block_till_done()
    client = await hass_client()
    req = await client.get(url)
    tts_data = b""
    tts_data = tts.SpeechManager.write_tags(
        f"42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_{expected_url_suffix}.mp3",
        tts_data,
        "Test",
        service_data[tts.ATTR_MESSAGE],
        "en",
        None,
    )
    assert req.status == HTTPStatus.OK
    assert await req.read() == tts_data

    extension, data = await tts.async_get_media_source_audio(
        hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]
    )
    assert extension == "mp3"
    assert tts_data == data


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MockProvider("de_DE"), MockTTSEntity("de_DE"))],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_receive_voice_german(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and call service and receive voice."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    assert len(calls) == 1
    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    await hass.async_block_till_done()
    client = await hass_client()
    req = await client.get(url)
    tts_data = b""
    tts_data = tts.SpeechManager.write_tags(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_de-de_-_{expected_url_suffix}.mp3",
        tts_data,
        "Test",
        "There is someone at the door.",
        "de",
        None,
    )
    assert req.status == HTTPStatus.OK
    assert await req.read() == tts_data


@pytest.mark.parametrize(
    ("setup", "expected_url_suffix"),
    [("mock_setup", "test"), ("mock_config_entry_setup", "tts.test")],
    indirect=["setup"],
)
async def test_web_view_wrong_file(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup: str,
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and receive wrong file from web."""
    client = await hass_client()

    url = (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        f"_en-us_-_{expected_url_suffix}.mp3"
    )

    req = await client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("setup", "expected_url_suffix"),
    [("mock_setup", "test"), ("mock_config_entry_setup", "tts.test")],
    indirect=["setup"],
)
async def test_web_view_wrong_filename(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup: str,
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and receive wrong filename from web."""
    client = await hass_client()

    url = (
        "/api/tts_proxy/265944dsk32c1b2a621be5930510bb2cd"
        f"_en-us_-_{expected_url_suffix}.mp3"
    )

    req = await client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data", "expected_url_suffix"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_CACHE: False,
            },
            "test",
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_CACHE: False,
            },
            "tts.test",
        ),
    ],
    indirect=["setup"],
)
async def test_service_without_cache(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform with cache and call service without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert not (
        mock_tts_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_{expected_url_suffix}.mp3"
    ).is_file()


class MockProviderBoom(MockProvider):
    """Mock provider that blows up."""

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Load TTS dat."""
        # This should not be called, data should be fetched from cache
        raise Exception("Boom!")  # pylint: disable=broad-exception-raised


class MockEntityBoom(MockTTSEntity):
    """Mock entity that blows up."""

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Load TTS dat."""
        # This should not be called, data should be fetched from cache
        raise Exception("Boom!")  # pylint: disable=broad-exception-raised


@pytest.mark.parametrize("mock_provider", [MockProviderBoom(DEFAULT_LANG)])
async def test_setup_legacy_cache_dir(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    mock_provider: MockProvider,
) -> None:
    """Set up a TTS platform with cache and call service without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    tts_data = b""
    cache_file = (
        mock_tts_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_test.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(tts_data)

    await mock_setup(hass, mock_provider)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            ATTR_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_test.mp3"
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize("mock_tts_entity", [MockEntityBoom(DEFAULT_LANG)])
async def test_setup_cache_dir(
    hass: HomeAssistant,
    mock_tts_cache_dir,
    mock_tts_entity: MockTTSEntity,
) -> None:
    """Set up a TTS platform with cache and call service without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    tts_data = b""
    cache_file = mock_tts_cache_dir / (
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_tts.test.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(tts_data)

    await mock_config_entry_setup(hass, mock_tts_entity)

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: "tts.test",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]) == (
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_tts.test.mp3"
    )
    await hass.async_block_till_done()


class MockProviderEmpty(MockProvider):
    """Mock provider with empty get_tts_audio."""

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Load TTS dat."""
        return (None, None)


class MockEntityEmpty(MockTTSEntity):
    """Mock entity with empty get_tts_audio."""

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> tts.TtsAudioType:
        """Load TTS dat."""
        return (None, None)


@pytest.mark.parametrize(
    ("mock_provider", "mock_tts_entity"),
    [(MockProviderEmpty(DEFAULT_LANG), MockEntityEmpty(DEFAULT_LANG))],
)
@pytest.mark.parametrize(
    ("setup", "tts_service", "service_data"),
    [
        (
            "mock_setup",
            "test_say",
            {
                ATTR_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        ),
        (
            "mock_config_entry_setup",
            "speak",
            {
                ATTR_ENTITY_ID: "tts.test",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
        ),
    ],
    indirect=["setup"],
)
async def test_service_get_tts_error(
    hass: HomeAssistant,
    setup: str,
    tts_service: str,
    service_data: dict[str, Any],
) -> None:
    """Set up a TTS platform with wrong get_tts_audio."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    await hass.services.async_call(
        tts.DOMAIN,
        tts_service,
        service_data,
        blocking=True,
    )
    assert len(calls) == 1
    with pytest.raises(Unresolvable):
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])


async def test_load_cache_legacy_retrieve_without_mem_cache(
    hass: HomeAssistant,
    mock_provider: MockProvider,
    mock_tts_cache_dir,
    hass_client: ClientSessionGenerator,
) -> None:
    """Set up component and load cache and get without mem cache."""
    tts_data = b""
    cache_file = (
        mock_tts_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(tts_data)

    await mock_setup(hass, mock_provider)

    client = await hass_client()

    url = "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.OK
    assert await req.read() == tts_data


async def test_load_cache_retrieve_without_mem_cache(
    hass: HomeAssistant,
    mock_tts_entity: MockTTSEntity,
    mock_tts_cache_dir,
    hass_client: ClientSessionGenerator,
) -> None:
    """Set up component and load cache and get without mem cache."""
    tts_data = b""
    cache_file = mock_tts_cache_dir / (
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_tts.test.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(tts_data)

    await mock_config_entry_setup(hass, mock_tts_entity)

    client = await hass_client()

    url = "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_tts.test.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.OK
    assert await req.read() == tts_data


@pytest.mark.parametrize(
    ("setup", "data", "expected_url_suffix"),
    [
        ("mock_setup", {"platform": "test"}, "test"),
        ("mock_setup", {"engine_id": "test"}, "test"),
        ("mock_config_entry_setup", {"engine_id": "tts.test"}, "tts.test"),
    ],
    indirect=["setup"],
)
async def test_web_get_url(
    hass_client: ClientSessionGenerator,
    setup: str,
    data: dict[str, Any],
    expected_url_suffix: str,
) -> None:
    """Set up a TTS platform and receive file from web."""
    client = await hass_client()

    url = "/api/tts_get_url"
    data |= {"message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.OK
    response = await req.json()
    assert response == {
        "url": (
            "http://example.local:8123/api/tts_proxy/"
            "42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_en-us_-_{expected_url_suffix}.mp3"
        ),
        "path": (
            "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
            f"_en-us_-_{expected_url_suffix}.mp3"
        ),
    }


@pytest.mark.parametrize(
    ("setup", "data"),
    [
        ("mock_setup", {"platform": "test"}),
        ("mock_setup", {"engine_id": "test"}),
        ("mock_setup", {"message": "There is someone at the door."}),
        ("mock_config_entry_setup", {"engine_id": "tts.test"}),
        ("mock_config_entry_setup", {"message": "There is someone at the door."}),
    ],
    indirect=["setup"],
)
async def test_web_get_url_missing_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup: str,
    data: dict[str, Any],
) -> None:
    """Set up a TTS platform and receive wrong file from web."""
    client = await hass_client()
    url = "/api/tts_get_url"

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.BAD_REQUEST


async def test_tags_with_wave() -> None:
    """Set up a TTS platform and call service and receive voice."""

    # below data represents an empty wav file
    tts_data = bytes.fromhex(
        "52 49 46 46 24 00 00 00 57 41 56 45 66 6d 74 20 10 00 00 00 01 00 02 00"
        + "22 56 00 00 88 58 01 00 04 00 10 00 64 61 74 61 00 00 00 00"
    )

    tagged_data = ORIG_WRITE_TAGS(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.wav",
        tts_data,
        "Test",
        "AI person is in front of your door.",
        "en",
        None,
    )

    assert tagged_data != tts_data


@pytest.mark.parametrize(
    ("setup", "result_engine"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
@pytest.mark.parametrize(
    ("engine", "language", "options", "cache", "result_query"),
    (
        (None, None, None, None, ""),
        (None, "de_DE", None, None, "language=de_DE"),
        (None, "de_DE", {"voice": "henk"}, None, "language=de_DE&voice=henk"),
        (None, "de_DE", None, True, "cache=true&language=de_DE"),
    ),
)
async def test_generate_media_source_id(
    hass: HomeAssistant,
    setup: str,
    result_engine: str,
    engine: str | None,
    language: str | None,
    options: dict[str, Any] | None,
    cache: bool | None,
    result_query: str,
) -> None:
    """Test generating a media source ID."""
    media_source_id = tts.generate_media_source_id(
        hass, "msg", engine, language, options, cache
    )

    assert media_source_id.startswith("media-source://tts/")
    _, _, engine_query = media_source_id.rpartition("/")
    engine, _, query = engine_query.partition("?")
    assert engine == result_engine
    assert query.startswith("message=msg")
    assert query[12:] == result_query


@pytest.mark.parametrize(
    "setup",
    [
        "mock_setup",
        "mock_config_entry_setup",
    ],
    indirect=["setup"],
)
@pytest.mark.parametrize(
    ("engine", "language", "options"),
    (
        ("not-loaded-engine", None, None),
        (None, "unsupported-language", None),
        (None, None, {"option": "not-supported"}),
    ),
)
async def test_generate_media_source_id_invalid_options(
    hass: HomeAssistant,
    setup: str,
    engine: str | None,
    language: str | None,
    options: dict[str, Any] | None,
) -> None:
    """Test generating a media source ID."""
    with pytest.raises(HomeAssistantError):
        tts.generate_media_source_id(hass, "msg", engine, language, options, None)


@pytest.mark.parametrize(
    ("setup", "engine_id"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
def test_resolve_engine(hass: HomeAssistant, setup: str, engine_id: str) -> None:
    """Test resolving engine."""
    assert tts.async_resolve_engine(hass, None) == engine_id
    assert tts.async_resolve_engine(hass, engine_id) == engine_id
    assert tts.async_resolve_engine(hass, "non-existing") is None

    with patch.dict(
        hass.data[tts.DATA_TTS_MANAGER].providers, {}, clear=True
    ), patch.dict(hass.data[tts.DOMAIN]._platforms, {}, clear=True):
        assert tts.async_resolve_engine(hass, None) is None

    with patch.dict(hass.data[tts.DATA_TTS_MANAGER].providers, {"cloud": object()}):
        assert tts.async_resolve_engine(hass, None) == "cloud"


@pytest.mark.parametrize(
    ("setup", "engine_id"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
async def test_support_options(hass: HomeAssistant, setup: str, engine_id: str) -> None:
    """Test supporting options."""
    assert await tts.async_support_options(hass, engine_id, "en_US") is True
    assert await tts.async_support_options(hass, engine_id, "nl") is False
    assert (
        await tts.async_support_options(
            hass, engine_id, "en_US", {"invalid_option": "yo"}
        )
        is False
    )

    with pytest.raises(HomeAssistantError):
        await tts.async_support_options(hass, "non-existing")


async def test_legacy_fetching_in_async(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test async fetching of data for a legacy provider."""
    tts_audio: asyncio.Future[bytes] = asyncio.Future()

    class ProviderWithAsyncFetching(MockProvider):
        """Provider that supports audio output option."""

        @property
        def supported_options(self) -> list[str]:
            """Return list of supported options like voice, emotions."""
            return [tts.ATTR_AUDIO_OUTPUT]

        @property
        def default_options(self) -> dict[str, str]:
            """Return a dict including the default options."""
            return {tts.ATTR_AUDIO_OUTPUT: "mp3"}

        async def async_get_tts_audio(
            self, message: str, language: str, options: dict[str, Any]
        ) -> tts.TtsAudioType:
            return ("mp3", await tts_audio)

    await mock_setup(hass, ProviderWithAsyncFetching(DEFAULT_LANG))

    # Test async_get_media_source_audio
    media_source_id = tts.generate_media_source_id(
        hass, "test message", "test", "en_US", None, None
    )

    task = hass.async_create_task(
        tts.async_get_media_source_audio(hass, media_source_id)
    )
    task2 = hass.async_create_task(
        tts.async_get_media_source_audio(hass, media_source_id)
    )

    url = await get_media_source_url(hass, media_source_id)
    client = await hass_client()
    client_get_task = hass.async_create_task(client.get(url))

    # Make sure that tasks are waiting for our future to resolve
    done, pending = await asyncio.wait((task, task2, client_get_task), timeout=0.1)
    assert len(done) == 0
    assert len(pending) == 3

    tts_audio.set_result(b"test")

    assert await task == ("mp3", b"test")
    assert await task2 == ("mp3", b"test")

    req = await client_get_task
    assert req.status == HTTPStatus.OK
    assert await req.read() == b"test"

    # Test error is not cached
    media_source_id = tts.generate_media_source_id(
        hass, "test message 2", "test", "en_US", None, None
    )
    tts_audio = asyncio.Future()
    tts_audio.set_exception(HomeAssistantError("test error"))
    with pytest.raises(HomeAssistantError):
        assert await tts.async_get_media_source_audio(hass, media_source_id)

    tts_audio = asyncio.Future()
    tts_audio.set_result(b"test 2")
    assert await tts.async_get_media_source_audio(hass, media_source_id) == (
        "mp3",
        b"test 2",
    )


async def test_fetching_in_async(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test async fetching of data."""
    tts_audio: asyncio.Future[bytes] = asyncio.Future()

    class EntityWithAsyncFetching(MockTTSEntity):
        """Entity that supports audio output option."""

        @property
        def supported_options(self) -> list[str]:
            """Return list of supported options like voice, emotions."""
            return [tts.ATTR_AUDIO_OUTPUT]

        @property
        def default_options(self) -> dict[str, str]:
            """Return a dict including the default options."""
            return {tts.ATTR_AUDIO_OUTPUT: "mp3"}

        async def async_get_tts_audio(
            self, message: str, language: str, options: dict[str, Any]
        ) -> tts.TtsAudioType:
            return ("mp3", await tts_audio)

    await mock_config_entry_setup(hass, EntityWithAsyncFetching(DEFAULT_LANG))

    # Test async_get_media_source_audio
    media_source_id = tts.generate_media_source_id(
        hass, "test message", "tts.test", "en_US", None, None
    )

    task = hass.async_create_task(
        tts.async_get_media_source_audio(hass, media_source_id)
    )
    task2 = hass.async_create_task(
        tts.async_get_media_source_audio(hass, media_source_id)
    )

    url = await get_media_source_url(hass, media_source_id)
    client = await hass_client()
    client_get_task = hass.async_create_task(client.get(url))

    # Make sure that tasks are waiting for our future to resolve
    done, pending = await asyncio.wait((task, task2, client_get_task), timeout=0.1)
    assert len(done) == 0
    assert len(pending) == 3

    tts_audio.set_result(b"test")

    assert await task == ("mp3", b"test")
    assert await task2 == ("mp3", b"test")

    req = await client_get_task
    assert req.status == HTTPStatus.OK
    assert await req.read() == b"test"

    # Test error is not cached
    media_source_id = tts.generate_media_source_id(
        hass, "test message 2", "tts.test", "en_US", None, None
    )
    tts_audio = asyncio.Future()
    tts_audio.set_exception(HomeAssistantError("test error"))
    with pytest.raises(HomeAssistantError):
        assert await tts.async_get_media_source_audio(hass, media_source_id)

    tts_audio = asyncio.Future()
    tts_audio.set_result(b"test 2")
    assert await tts.async_get_media_source_audio(hass, media_source_id) == (
        "mp3",
        b"test 2",
    )


@pytest.mark.parametrize(
    ("setup", "engine_id"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
async def test_ws_list_engines(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup: str, engine_id: str
) -> None:
    """Test listing tts engines and supported languages."""
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "tts/engine/list"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [
            {
                "engine_id": engine_id,
                "supported_languages": ["de_CH", "de_DE", "en_GB", "en_US"],
            }
        ]
    }

    await client.send_json_auto_id({"type": "tts/engine/list", "language": "smurfish"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [{"engine_id": engine_id, "supported_languages": []}]
    }

    await client.send_json_auto_id({"type": "tts/engine/list", "language": "en"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [
            {"engine_id": engine_id, "supported_languages": ["en_US", "en_GB"]}
        ]
    }

    await client.send_json_auto_id({"type": "tts/engine/list", "language": "en-UK"})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "providers": [
            {"engine_id": engine_id, "supported_languages": ["en_GB", "en_US"]}
        ]
    }

    await client.send_json_auto_id({"type": "tts/engine/list", "language": "de"})
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == {
        "providers": [
            {"engine_id": engine_id, "supported_languages": ["de_DE", "de_CH"]}
        ]
    }

    await client.send_json_auto_id(
        {"type": "tts/engine/list", "language": "de", "country": "ch"}
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == {
        "providers": [
            {"engine_id": engine_id, "supported_languages": ["de_CH", "de_DE"]}
        ]
    }


@pytest.mark.parametrize(
    ("setup", "engine_id"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
async def test_ws_get_engine(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup: str, engine_id: str
) -> None:
    """Test getting an tts engine."""
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "tts/engine/get", "engine_id": engine_id})

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "provider": {
            "engine_id": engine_id,
            "supported_languages": ["de_CH", "de_DE", "en_GB", "en_US"],
        }
    }


@pytest.mark.parametrize(
    ("setup", "engine_id"),
    [("mock_setup", "not_existing"), ("mock_config_entry_setup", "tts.not_existing")],
    indirect=["setup"],
)
async def test_ws_get_engine_none_existing(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup: str, engine_id: str
) -> None:
    """Test getting a non existing tts engine."""
    client = await hass_ws_client()

    await client.send_json_auto_id({"type": "tts/engine/get", "engine_id": engine_id})

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


@pytest.mark.parametrize(
    ("setup", "engine_id"),
    [
        ("mock_setup", "test"),
        ("mock_config_entry_setup", "tts.test"),
    ],
    indirect=["setup"],
)
async def test_ws_list_voices(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, setup: str, engine_id: str
) -> None:
    """Test listing supported voices for a tts engine and language."""
    client = await hass_ws_client()

    await client.send_json_auto_id(
        {
            "type": "tts/engine/voices",
            "engine_id": "smurf_tts",
            "language": "smurfish",
        }
    )

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "not_found",
        "message": "tts engine smurf_tts not found",
    }

    await client.send_json_auto_id(
        {
            "type": "tts/engine/voices",
            "engine_id": engine_id,
            "language": "smurfish",
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"voices": None}

    await client.send_json_auto_id(
        {
            "type": "tts/engine/voices",
            "engine_id": engine_id,
            "language": "en-US",
        }
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "voices": [
            {"voice_id": "james_earl_jones", "name": "James Earl Jones"},
            {"voice_id": "fran_drescher", "name": "Fran Drescher"},
        ]
    }
