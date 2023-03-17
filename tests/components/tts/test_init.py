"""The tests for the TTS component."""
from http import HTTPStatus
from unittest.mock import PropertyMock, patch

import pytest
import voluptuous as vol

from homeassistant.components import media_source, tts
from homeassistant.components.demo.tts import DemoProvider
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util.network import normalize_url

from tests.common import assert_setup_component, async_mock_service
from tests.typing import ClientSessionGenerator

ORIG_WRITE_TAGS = tts.SpeechManager.write_tags


async def get_media_source_url(hass, media_content_id):
    """Get the media source url."""
    if media_source.DOMAIN not in hass.config.components:
        assert await async_setup_component(hass, media_source.DOMAIN, {})

    resolved = await media_source.async_resolve_media(hass, media_content_id, None)
    return resolved.url


@pytest.fixture
def demo_provider():
    """Demo TTS provider."""
    return DemoProvider("en")


@pytest.fixture(autouse=True)
async def internal_url_mock(hass):
    """Mock internal URL of the instance."""
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )


@pytest.fixture
async def setup_tts(hass):
    """Mock TTS."""
    with patch("homeassistant.components.demo.async_setup", return_value=True):
        assert await async_setup_component(
            hass, tts.DOMAIN, {"tts": {"platform": "demo"}}
        )
        await hass.async_block_till_done()


async def test_setup_component_demo(hass: HomeAssistant, setup_tts) -> None:
    """Set up the demo platform with defaults."""
    assert hass.services.has_service(tts.DOMAIN, "demo_say")
    assert hass.services.has_service(tts.DOMAIN, "clear_cache")
    assert f"{tts.DOMAIN}.demo" in hass.config.components


async def test_setup_component_demo_no_access_cache_folder(
    hass: HomeAssistant, mock_init_cache_dir
) -> None:
    """Set up the demo platform with defaults."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    mock_init_cache_dir.side_effect = OSError(2, "No access")
    assert not await async_setup_component(hass, tts.DOMAIN, config)

    assert not hass.services.has_service(tts.DOMAIN, "demo_say")
    assert not hass.services.has_service(tts.DOMAIN, "clear_cache")


async def test_setup_component_and_test_service(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_config_language(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo", "language": "de"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_config_language_special(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service with extend language."""
    import homeassistant.components.demo.tts as demo_tts

    demo_tts.SUPPORT_LANGUAGES.append("en_US")
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo", "language": "en_US"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_demo.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en-us_-_demo.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_wrong_conf_language(
    hass: HomeAssistant,
) -> None:
    """Set up the demo platform and call service with wrong config."""
    config = {tts.DOMAIN: {"platform": "demo", "language": "ru"}}

    with assert_setup_component(0, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)


async def test_setup_component_and_test_service_with_service_language(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3"
    ).is_file()


async def test_setup_component_test_service_with_wrong_service_language(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
                tts.ATTR_LANGUAGE: "lang",
            },
            blocking=True,
        )
    assert len(calls) == 0
    assert not (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_lang_-_demo.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_service_options(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service with options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        == f"/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_demo.mp3"
    )
    await hass.async_block_till_done()
    assert (
        empty_cache_dir
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_demo.mp3"
    ).is_file()


async def test_setup_component_and_test_with_service_options_def(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service with default options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN), patch(
        "homeassistant.components.demo.tts.DemoProvider.default_options",
        new_callable=PropertyMock(return_value={"voice": "alex"}),
    ):
        assert await async_setup_component(hass, tts.DOMAIN, config)

        await hass.services.async_call(
            tts.DOMAIN,
            "demo_say",
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
            == f"/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_demo.mp3"
        )
        await hass.async_block_till_done()
        assert (
            empty_cache_dir
            / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_demo.mp3"
        ).is_file()


async def test_setup_component_and_test_service_with_service_options_wrong(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service with wrong options."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            tts.DOMAIN,
            "demo_say",
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
        / f"42f18378fd4393d18c8dd11d03fa9563c1e54491_de_{opt_hash}_demo.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_base_url_set(
    hass: HomeAssistant,
) -> None:
    """Set up the demo platform with ``base_url`` set and call service."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo", "base_url": "http://fnord"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        "_en_-_demo.mp3"
    )


async def test_setup_component_and_test_service_clear_cache(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up the demo platform and call service clear cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    ).is_file()

    await hass.services.async_call(
        tts.DOMAIN, tts.SERVICE_CLEAR_CACHE, {}, blocking=True
    )

    assert not (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    ).is_file()


async def test_setup_component_and_test_service_with_receive_voice(
    hass: HomeAssistant, demo_provider, hass_client: ClientSessionGenerator
) -> None:
    """Set up the demo platform and call service and receive voice."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    message = "There is someone at the door."

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
    _, demo_data = demo_provider.get_tts_audio("bla", "en")
    demo_data = tts.SpeechManager.write_tags(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
        demo_data,
        demo_provider,
        message,
        "en",
        None,
    )
    assert req.status == HTTPStatus.OK
    assert await req.read() == demo_data

    extension, data = await tts.async_get_media_source_audio(
        hass, calls[0].data[ATTR_MEDIA_CONTENT_ID]
    )
    assert extension == "mp3"
    assert demo_data == data


async def test_setup_component_and_test_service_with_receive_voice_german(
    hass: HomeAssistant, demo_provider, hass_client: ClientSessionGenerator
) -> None:
    """Set up the demo platform and call service and receive voice."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo", "language": "de"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
    _, demo_data = demo_provider.get_tts_audio("bla", "de")
    demo_data = tts.SpeechManager.write_tags(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_de_-_demo.mp3",
        demo_data,
        demo_provider,
        "There is someone at the door.",
        "de",
        None,
    )
    assert req.status == HTTPStatus.OK
    assert await req.read() == demo_data


async def test_setup_component_and_web_view_wrong_file(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Set up the demo platform and receive wrong file from web."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


async def test_setup_component_and_web_view_wrong_filename(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Set up the demo platform and receive wrong filename from web."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_proxy/265944dsk32c1b2a621be5930510bb2cd_en_-_demo.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.NOT_FOUND


async def test_setup_component_test_without_cache(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up demo platform without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo", "cache": False}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
        {
            "entity_id": "media_player.something",
            tts.ATTR_MESSAGE: "There is someone at the door.",
        },
        blocking=True,
    )
    assert len(calls) == 1
    await hass.async_block_till_done()
    assert not (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    ).is_file()


async def test_setup_component_test_with_cache_call_service_without_cache(
    hass: HomeAssistant, empty_cache_dir
) -> None:
    """Set up demo platform with cache and call service without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "demo", "cache": True}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    await hass.services.async_call(
        tts.DOMAIN,
        "demo_say",
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
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    ).is_file()


async def test_setup_component_test_with_cache_dir(
    hass: HomeAssistant, empty_cache_dir, demo_provider
) -> None:
    """Set up demo platform with cache and call service without cache."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    _, demo_data = demo_provider.get_tts_audio("bla", "en")
    cache_file = (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(demo_data)

    config = {tts.DOMAIN: {"platform": "demo", "cache": True}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    with patch(
        "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
        return_value=(None, None),
    ):
        await hass.services.async_call(
            tts.DOMAIN,
            "demo_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "There is someone at the door.",
            },
            blocking=True,
        )
    assert len(calls) == 1
    assert (
        await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    )


async def test_setup_component_test_with_error_on_get_tts(hass: HomeAssistant) -> None:
    """Set up demo platform with wrong get_tts_audio."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, tts.DOMAIN), patch(
        "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
        return_value=(None, None),
    ):
        assert await async_setup_component(hass, tts.DOMAIN, config)


async def test_setup_component_load_cache_retrieve_without_mem_cache(
    hass: HomeAssistant,
    demo_provider,
    empty_cache_dir,
    hass_client: ClientSessionGenerator,
) -> None:
    """Set up component and load cache and get without mem cache."""
    _, demo_data = demo_provider.get_tts_audio("bla", "en")
    cache_file = (
        empty_cache_dir / "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"
    )

    with open(cache_file, "wb") as voice_file:
        voice_file.write(demo_data)

    config = {tts.DOMAIN: {"platform": "demo", "cache": True}}

    with assert_setup_component(1, tts.DOMAIN):
        assert await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3"

    req = await client.get(url)
    assert req.status == HTTPStatus.OK
    assert await req.read() == demo_data


async def test_setup_component_and_web_get_url(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Set up the demo platform and receive file from web."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_get_url"
    data = {"platform": "demo", "message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.OK
    response = await req.json()
    assert response == {
        "url": "http://example.local:8123/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
        "path": "/api/tts_proxy/42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.mp3",
    }


async def test_setup_component_and_web_get_url_bad_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Set up the demo platform and receive wrong file from web."""
    config = {tts.DOMAIN: {"platform": "demo"}}

    await async_setup_component(hass, tts.DOMAIN, config)

    client = await hass_client()

    url = "/api/tts_get_url"
    data = {"message": "There is someone at the door."}

    req = await client.post(url, json=data)
    assert req.status == HTTPStatus.BAD_REQUEST


async def test_tags_with_wave(hass: HomeAssistant, demo_provider) -> None:
    """Set up the demo platform and call service and receive voice."""

    # below data represents an empty wav file
    demo_data = bytes.fromhex(
        "52 49 46 46 24 00 00 00 57 41 56 45 66 6d 74 20 10 00 00 00 01 00 02 00"
        + "22 56 00 00 88 58 01 00 04 00 10 00 64 61 74 61 00 00 00 00"
    )

    tagged_data = ORIG_WRITE_TAGS(
        "42f18378fd4393d18c8dd11d03fa9563c1e54491_en_-_demo.wav",
        demo_data,
        demo_provider,
        "AI person is in front of your door.",
        "en",
        None,
    )

    assert tagged_data != demo_data


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
        (None, None, None, None, "demo", ""),
        (None, "de", None, None, "demo", "language=de"),
        (None, "de", {"voice": "henk"}, None, "demo", "language=de&voice=henk"),
        (None, "de", None, True, "demo", "cache=true&language=de"),
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
