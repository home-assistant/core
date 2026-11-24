"""The tests for the Pico TTS speech platform."""

from http import HTTPStatus
import io
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
import wave

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import tts
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID
from homeassistant.components.picotts.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError

from tests.components.tts.common import retrieve_media


async def get_tts_audio(hass: HomeAssistant) -> bytes:
    """Get TTS audio from the Pico TTS entity."""
    stream = tts.async_create_stream(hass, "tts.pico_tts_en_us", "en-US")
    stream.async_set_message("Hello world")
    return b"".join([chunk async for chunk in stream.async_stream_result()])


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
async def setup_picotts(
    hass: HomeAssistant,
    mock_nanotts: MagicMock,
    config: dict[str, Any],
) -> None:
    """Set up picotts integration via config entry."""
    default_config = {tts.CONF_LANG: "en-US"}
    config_entry = MockConfigEntry(domain=DOMAIN, data=default_config | config)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Return config."""
    return {}


@pytest.mark.usefixtures("setup_picotts")
@pytest.mark.parametrize(
    ("config", "entity_id", "extra_service_data", "expected_voice"),
    [
        ({}, "tts.pico_tts_en_us", {}, "en-US"),
        ({tts.CONF_LANG: "de-DE"}, "tts.pico_tts_de_de", {}, "de-DE"),
        ({}, "tts.pico_tts_en_us", {tts.ATTR_LANGUAGE: "de-DE"}, "de-DE"),
        ({tts.CONF_LANG: "en-GB"}, "tts.pico_tts_en_gb", {}, "en-GB"),
        ({}, "tts.pico_tts_en_us", {tts.ATTR_LANGUAGE: "en-GB"}, "en-GB"),
    ],
)
async def test_tts_service(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    mock_nanotts: MagicMock,
    entity_id: str,
    extra_service_data: dict[str, Any],
    expected_voice: str,
) -> None:
    """Test tts speak service with various language configurations."""
    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: entity_id,
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            **extra_service_data,
        },
        blocking=True,
    )

    assert len(service_calls) == 2
    assert (
        await retrieve_media(
            hass, hass_client, service_calls[1].data[ATTR_MEDIA_CONTENT_ID]
        )
        == HTTPStatus.OK
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_nanotts.speak.assert_called_once_with(
        "There is a person at the front door.", voice=expected_voice
    )


@pytest.mark.usefixtures("setup_picotts")
async def test_get_tts_audio_wav(
    hass: HomeAssistant,
    mock_nanotts: MagicMock,
) -> None:
    """Test raw PCM from the engine is wrapped in a WAV container."""
    # Use the entity directly, since the TTS stream converts to MP3
    entity = hass.data[tts.DOMAIN].get_entity("tts.pico_tts_en_us")
    extension, data = await entity.async_get_tts_audio("Hello world", "en-US", {})

    assert extension == "wav"
    with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnchannels() == 1
        assert (
            wav_file.readframes(wav_file.getnframes())
            == mock_nanotts.speak.return_value
        )


@pytest.mark.usefixtures("setup_picotts")
async def test_get_tts_audio_error(
    hass: HomeAssistant,
    mock_nanotts: MagicMock,
) -> None:
    """Test get_tts_audio when synthesis fails."""
    mock_nanotts.speak.side_effect = RuntimeError("pico_putTextUtf8 failed")

    with pytest.raises(HomeAssistantError) as exc_info:
        await get_tts_audio(hass)

    assert exc_info.value.translation_key == "synthesis_error"
    assert exc_info.value.translation_placeholders == {
        "error": "pico_putTextUtf8 failed"
    }
