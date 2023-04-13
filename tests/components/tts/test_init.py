"""The tests for the TTS component."""
import asyncio
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components import media_source, tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.components.media_source import Unresolvable
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component
from homeassistant.util.network import normalize_url

from tests.common import (
    MockModule,
    assert_setup_component,
    async_mock_service,
    mock_integration,
    mock_platform,
)
from tests.typing import ClientSessionGenerator

ORIG_WRITE_TAGS = tts.SpeechManager.write_tags


async def get_media_source_url(hass, media_content_id):
    """Get the media source url."""
    if media_source.DOMAIN not in hass.config.components:
        assert await async_setup_component(hass, media_source.DOMAIN, {})

    resolved = await media_source.async_resolve_media(hass, media_content_id, None)
    return resolved.url


SUPPORT_LANGUAGES = ["de", "en", "en_US"]

DEFAULT_LANG = "en"


class MockProvider(tts.Provider):
    """Test speech API provider."""

    def __init__(self, lang: str) -> None:
        """Initialize test provider."""
        self._lang = lang
        self.name = "Test"

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._lang

    @property
    def supported_languages(self) -> list[str]:
        """Return list of supported languages."""
        return SUPPORT_LANGUAGES

    @property
    def supported_options(self) -> list[str]:
        """Return list of supported options like voice, emotions."""
        return ["voice", "age"]

    def get_tts_audio(
        self, message: str, language: str, options: dict[str, Any] | None = None
    ) -> tts.TtsAudioType:
        """Load TTS dat."""
        return ("mp3", b"")


class MockTTS:
    """A mock TTS platform."""

    PLATFORM_SCHEMA = tts.PLATFORM_SCHEMA.extend(
        {vol.Optional(tts.CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES)}
    )

    def __init__(self, provider=None) -> None:
        """Initialize."""
        if provider is None:
            provider = MockProvider
        self._provider = provider

    async def async_get_engine(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> tts.Provider:
        """Set up a mock speech component."""
        return self._provider(config.get(tts.CONF_LANG, DEFAULT_LANG))


@pytest.fixture
def test_provider():
    """Test TTS provider."""
    return MockProvider("en")


@pytest.fixture(autouse=True)
async def internal_url_mock(hass):
    """Mock internal URL of the instance."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )


@pytest.fixture
async def mock_tts(hass):
    """Mock TTS."""
    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS())


@pytest.fixture
async def setup_tts(hass, mock_tts):
    """Mock TTS."""
    assert await async_setup_component(hass, tts.DOMAIN, {"tts": {"platform": "test"}})


async def test_setup_component(hass: HomeAssistant, setup_tts) -> None:
    """Set up a TTS platform with defaults."""
    assert hass.services.has_service(tts.DOMAIN, "test_say")
    assert hass.services.has_service(tts.DOMAIN, "clear_cache")
    assert f"{tts.DOMAIN}.test" in hass.config.components


async def test_setup_component_no_access_cache_folder(
    hass: HomeAssistant, mock_init_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform with defaults."""
    config = {tts.DOMAIN: {"platform": "test"}}

    mock_init_cache_dir.side_effect = OSError(2, "No access")
    assert not await async_setup_component(hass, tts.DOMAIN, config)

    assert not hass.services.has_service(tts.DOMAIN, "test_say")
    assert not hass.services.has_service(tts.DOMAIN, "clear_cache")


async def test_setup_component_and_test_service(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_ANNOUNCE] is True
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_config_language(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test", "language": "de"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_test.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_test.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_config_language_special(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service with extend language."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test", "language": "en_US"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_test.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_test.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_wrong_conf_language(
    hass: HomeAssistant, mock_tts
) -> None:
    """Set up a TTS platform and call service with wrong config."""
    config = {tts.DOMAIN: {"platform": "test", "language": "ru"}}

    with assert_setup_component(0, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)


async def test_setup_component_and_test_service_with_service_language(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
            tts.ATTR_LANGUAGE: "de",
        },
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_test.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_test.mp3"
    ).is_file()


async def test_setup_component_test_service_with_wrong_service_language(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            tts.DOMAIN,
            "test_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "lang",
            },
            blocking=True,
        )
    assert len(calls) == 0
    assert not (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_lang_-_test.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_service_options(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service with options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
            tts.ATTR_LANGUAGE: "de",
            tts.ATTR_OPTIONS: {"voice": "alex", "age": 5},
        },
        blocking=True,
    )
    opt_hash = tts._hash_options({"voice": "alex", "age": 5})

    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == f"/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_test.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_test.mp3"
    ).is_file()


async def test_setup_component_and_test_with_service_options_def(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up a TTS platform and call service with default options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    class MockProviderWithDefaults(MockProvider):
        @property
        def default_options(self):
            return {"voice": "alex"}

    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS(MockProviderWithDefaults))

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

        await hass.services.async_call(
            tts.DOMAIN,
            "test_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de",
            },
            blocking=True,
        )
        opt_hash = tts._hash_options({"voice": "alex"})

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
        assert (
            await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
            == f"/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_test.mp3"
        )
        await hass.async_block_till_done()
        assert (
            empty_cache_dir
            / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_test.mp3"
        ).is_file()


async def test_setup_component_and_test_with_service_options_def_2(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up a TTS platform and call service with default options.

    This tests merging default and user provided options.
    """
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    class MockProviderWithDefaults(MockProvider):
        @property
        def default_options(self):
            return {"voice": "alex"}

    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS(MockProviderWithDefaults))

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

        await hass.services.async_call(
            tts.DOMAIN,
            "test_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de",
                tts.ATTR_OPTIONS: {"age": 5},
            },
            blocking=True,
        )
        opt_hash = tts._hash_options({"voice": "alex", "age": 5})

        assert len(calls) == 1
        assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
        assert (
            await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
            == f"/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_test.mp3"
        )
        await hass.async_block_till_done()
        assert (
            empty_cache_dir
            / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_test.mp3"
        ).is_file()


async def test_setup_component_and_test_service_with_service_options_wrong(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service with wrong options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            tts.DOMAIN,
            "test_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "de",
                tts.ATTR_OPTIONS: {"speed": 1},
            },
            blocking=True,
        )
    opt_hash = tts._hash_options({"speed": 1})

    assert len(calls) == 0
    await hass.async_block_till_done()
    assert not (
        empty_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_test.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_base_url_set(
    hass: HomeAssistant, mock_tts
) -> None:
    """Set up a TTS platform with ``base_url`` set and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test", "base_url": "http://fnord"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    assert calls[0].data[ATTR_MEDIA_CONTENT_TYPE] == MediaType.MUSIC
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == "http://fnord"
        "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491"
        "_en_-_test.mp3"
    )


async def test_setup_component_and_test_service_clear_cache(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform and call service clear cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    # To make sure the file is persisted
    assert len(calls) == 1
    await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    ).is_file()

    await hass.services.async_call(
        tts.DOMAIN, tts.SERVICE_CLEAR_CACHE, {}, blocking=True
    )

    assert not (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_receive_voice(
    hass: HomeAssistant, test_provider, hass_client: ClientSessionGenerator, mock_tts
) -> None:
    """Set up a TTS platform and call service and receive voice."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    message = "There is someone at the door."

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: message,
        },
        blocking=True,
    )
    assert len(calls) == 1

    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    client = await hass_client()
    req = await client.get(url)
    _, tts_data = test_provider.get_tts_audio("bla", "en")
    tts_data = tts.SpeechManager.write_tags(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3",
        tts_data,
        test_provider,
        message,
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


async def test_setup_component_and_test_service_with_receive_voice_german(
    hass: HomeAssistant, test_provider, hass_client: ClientSessionGenerator, mock_tts
) -> None:
    """Set up a TTS platform and call service and receive voice."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test", "language": "de"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
    client = await hass_client()
    req = await client.get(url)
    _, tts_data = test_provider.get_tts_audio("bla", "de")
    tts_data = tts.SpeechManager.write_tags(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_test.mp3",
        tts_data,
        test_provider,
        "There is someone at the door.",
        "de",
        None,
    )
    assert req.status == HTTPStatus.OK
    assert await req.read() == tts_data


async def test_setup_component_and_web_view_wrong_file(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_tts
) -> None:
    """Set up a TTS platform and receive wrong file from web."""
    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


async def test_setup_component_and_web_view_wrong_filename(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_tts
) -> None:
    """Set up a TTS platform and receive wrong filename from web."""
    config = {tts.DOMAIN: {"platform": "test"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_proxy/265944dsk32c1b2a621be5930510bb2cd_en_-_test.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


async def test_setup_component_test_without_cache(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test", "cache": False}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert not (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    ).is_file()


async def test_setup_component_test_with_cache_call_service_without_cache(
    hass: HomeAssistant, empty_cache_dir, mock_tts
) -> None:
    """Set up a TTS platform with cache and call service without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test", "cache": True}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
            tts.ATTR_CACHE: False,
        },
        blocking=True,
    )
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert not (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    ).is_file()


async def test_setup_component_test_with_cache_dir(
    hass: HomeAssistant, empty_cache_dir, test_provider
) -> None:
    """Set up a TTS platform with cache and call service without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    _, tts_data = test_provider.get_tts_audio("bla", "en")
    cache_file = (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(tts_data)

    config = {tts.DOMAIN: {"platform": "test", "cache": True}}

    class MockProviderBoom(MockProvider):
        def get_tts_audio(
            self, message: str, language: str, options: dict[str, Any] | None = None
        ) -> tts.TtsAudioType:
            """Load TTS dat."""
            # This should not be called, data should be fetched from cache
            raise Exception("Boom!")

    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS(MockProviderBoom))

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    )


async def test_setup_component_test_with_error_on_get_tts(hass: HomeAssistant) -> None:
    """Set up a TTS platform with wrong get_tts_audio."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "test"}}

    class MockProviderEmpty(MockProvider):
        def get_tts_audio(
            self, message: str, language: str, options: dict[str, Any] | None = None
        ) -> tts.TtsAudioType:
            """Load TTS dat."""
            return (None, None)

    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS(MockProviderEmpty))

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "test_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    with pytest.raises(Unresolvable):
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])


async def test_setup_component_load_cache_retrieve_without_mem_cache(
    hass: HomeAssistant,
    test_provider,
    empty_cache_dir,
    hass_client: ClientSessionGenerator,
    mock_tts,
) -> None:
    """Set up component and load cache and get without mem cache."""
    _, tts_data = test_provider.get_tts_audio("bla", "en")
    cache_file = (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(tts_data)

    config = {tts.DOMAIN: {"platform": "test", "cache": True}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.OK
    assert await req.read() == tts_data


async def test_setup_component_and_web_get_url(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_tts
) -> None:
    """Set up a TTS platform and receive file from web."""
    config = {tts.DOMAIN: {"platform": "test"}}

    await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_get_url"
    data = {"platform": "test", "message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.OK
    response = await req.json()
    assert response == {
        "url": "http://example.local:8123/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3",
        "path": "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.mp3",
    }


async def test_setup_component_and_web_get_url_bad_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_tts
) -> None:
    """Set up a TTS platform and receive wrong file from web."""
    config = {tts.DOMAIN: {"platform": "test"}}

    await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_get_url"
    data = {"message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.BAD_REQUEST


async def test_tags_with_wave(hass: HomeAssistant, test_provider) -> None:
    """Set up a TTS platform and call service and receive voice."""

    # below data represents an empty wav file
    tts_data = bytes.fromhex(
        "52 49 46 46 24 00 00 00 57 41 56 45 66 6d 74 20 10 00 00 00 01 00 02 00"
        + "22 56 00 00 88 58 01 00 04 00 10 00 64 61 74 61 00 00 00 00"
    )

    tagged_data = ORIG_WRITE_TAGS(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_test.wav",
        tts_data,
        test_provider,
        "AI person is in front of your door.",
        "en",
        None,
    )

    assert tagged_data != tts_data


@pytest.mark.parametrize(
    "value",
    (
        "http://example.local:8123",
        "http://example.local",
        "http://example.local:80",
        "https://example.com",
        "https://example.com:443",
        "https://example.com:8123",
    ),
)
def test_valid_base_url(value) -> None:
    """Test we validate base urls."""
    assert tts.valid_base_url(value) == normalize_url(value)
    # Test we strip trailing `/`
    assert tts.valid_base_url(value + "/") == normalize_url(value)


@pytest.mark.parametrize(
    "value",
    (
        "http://example.local:8123/sub-path",
        "http://example.local/sub-path",
        "https://example.com/sub-path",
        "https://example.com:8123/sub-path",
        "mailto:some@email",
        "http:example.com",
        "http:/example.com",
        "http//example.com",
        "example.com",
    ),
)
def test_invalid_base_url(value) -> None:
    """Test we catch bad base urls."""
    with pytest.raises(vol.Invalid):
        tts.valid_base_url(value)


@pytest.mark.parametrize(
    ("engine", "language", "options", "cache", "result_engine", "result_query"),
    (
        (None, None, None, None, "test", ""),
        (None, "de", None, None, "test", "language=de"),
        (None, "de", {"voice": "henk"}, None, "test", "language=de&voice=henk"),
        (None, "de", None, True, "test", "cache=true&language=de"),
    ),
)
async def test_generate_media_source_id(
    hass: HomeAssistant,
    setup_tts,
    engine,
    language,
    options,
    cache,
    result_engine,
    result_query,
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
    ("engine", "language", "options"),
    (
        ("not-loaded-engine", None, None),
        (None, "unsupported-language", None),
        (None, None, {"option": "not-supported"}),
    ),
)
async def test_generate_media_source_id_invalid_options(
    hass: HomeAssistant, setup_tts, engine, language, options
) -> None:
    """Test generating a media source ID."""
    with pytest.raises(HomeAssistantError):
        tts.generate_media_source_id(hass, "msg", engine, language, options, None)


def test_resolve_engine(hass: HomeAssistant, setup_tts) -> None:
    """Test resolving engine."""
    assert tts.async_resolve_engine(hass, None) == "test"
    assert tts.async_resolve_engine(hass, "test") == "test"
    assert tts.async_resolve_engine(hass, "non-existing") is None

    with patch.dict(hass.data[tts.DOMAIN].providers, {}, clear=True):
        assert tts.async_resolve_engine(hass, "test") is None

    with patch.dict(hass.data[tts.DOMAIN].providers, {"cloud": object()}):
        assert tts.async_resolve_engine(hass, None) == "cloud"


async def test_support_options(hass: HomeAssistant, setup_tts) -> None:
    """Test supporting options."""
    assert await tts.async_support_options(hass, "test", "en") is True
    assert await tts.async_support_options(hass, "test", "nl") is False
    assert (
        await tts.async_support_options(hass, "test", "en", {"invalid_option": "yo"})
        is False
    )


async def test_fetching_in_async(hass: HomeAssistant, hass_client) -> None:
    """Test async fetching of data."""
    tts_audio = asyncio.Future()

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
            self, message: str, language: str, options: dict[str, Any] | None = None
        ) -> tts.TtsAudioType:
            return ("mp3", await tts_audio)

    mock_integration(hass, MockModule(domain="test"))
    mock_platform(hass, "test.tts", MockTTS(ProviderWithAsyncFetching))
    assert await async_setup_component(hass, tts.DOMAIN, {"tts": {"platform": "test"}})

    # Test async_get_media_source_audio
    media_source_id = tts.generate_media_source_id(
        hass, "test message", "test", "en", None, None
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
        hass, "test message 2", "test", "en", None, None
    )
    tts_audio = asyncio.Future()
    tts_audio.set_exception(HomeAssistantError("test error"))
    with pytest.raises(HomeAssistantError):
        assert await tts.async_get_media_source_audio(hass, media_source_id)

    tts_audio = asyncio.Future()
    tts_audio.set_result(b"test 2")
    await tts.async_get_media_source_audio(hass, media_source_id) == ("mp3", b"test 2")
