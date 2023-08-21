"""The tests for the MaryTTS speech platform."""
from unittest.mock import patch

import pytest

from homeassistant.components import media_source, tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_mock_service


async def get_media_source_url(hass, media_content_id):
    """Get the media source url."""
    if media_source.DOMAIN not in hass.config.components:
        assert await async_setup_component(hass, media_source.DOMAIN, {})

    resolved = await media_source.async_resolve_media(hass, media_content_id, None)
    return resolved.url


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir):
    """Mock the TTS cache dir with empty dir."""
    return mock_tts_cache_dir


async def test_setup_component(hass: HomeAssistant) -> None:
    """Test setup component."""
    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()


async def test_service_say(hass: HomeAssistant) -> None:
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        return_value=b"audio",
    ) as mock_speak:
        await hass.services.async_call(
            tts.DOMAIN,
            "marytts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "HomeAssistant",
            },
            blocking=True,
        )

        url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])

    mock_speak.assert_called_once()
    mock_speak.assert_called_with("HomeAssistant", {})

    assert len(calls) == 1
    assert url.endswith(".wav")


async def test_service_say_with_effect(hass: HomeAssistant) -> None:
    """Test service call say with effects."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts", "effect": {"Volume": "amount:2.0;"}}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        return_value=b"audio",
    ) as mock_speak:
        await hass.services.async_call(
            tts.DOMAIN,
            "marytts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "HomeAssistant",
            },
            blocking=True,
        )

        url = await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])

    mock_speak.assert_called_once()
    mock_speak.assert_called_with("HomeAssistant", {"Volume": "amount:2.0;"})

    assert len(calls) == 1
    assert url.endswith(".wav")


async def test_service_say_http_error(hass: HomeAssistant) -> None:
    """Test service call say."""
    calls = async_mock_service(hass, DOMAIN_MP, SERVICE_PLAY_MEDIA)

    config = {tts.DOMAIN: {"platform": "marytts"}}

    with assert_setup_component(1, tts.DOMAIN):
        await async_setup_component(hass, tts.DOMAIN, config)
        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.marytts.tts.MaryTTS.speak",
        side_effect=Exception(),
    ) as mock_speak:
        await hass.services.async_call(
            tts.DOMAIN,
            "marytts_say",
            {
                "entity_id": "media_player.something",
                tts.ATTR_MESSAGE: "HomeAssistant",
            },
        )
        await hass.async_block_till_done()

        with pytest.raises(Exception):
            await get_media_source_url(hass, calls[0].data[ATTR_MEDIA_CONTENT_ID])

    mock_speak.assert_called_once()
