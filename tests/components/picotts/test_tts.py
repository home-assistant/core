"""The tests for the Pico TTS speech platform."""

from __future__ import annotations

from http import HTTPStatus
import io
from pathlib import Path
import subprocess
from typing import Any
from unittest.mock import MagicMock, mock_open, patch
import wave

import pytest

from homeassistant.components import tts
from homeassistant.components.media_player import ATTR_MEDIA_CONTENT_ID
from homeassistant.components.picotts.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry
from tests.components.tts.common import retrieve_media
from tests.typing import ClientSessionGenerator


def get_empty_wav() -> bytes:
    """Get bytes for empty WAV file."""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setframerate(22050)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(bytes(22050 * 2))
        return wav_io.getvalue()


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
    config: dict[str, Any],
) -> None:
    """Set up picotts integration via config entry."""
    default_config = {tts.CONF_LANG: "en-US"}
    config_entry = MockConfigEntry(domain=DOMAIN, data=default_config | config)
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.picotts.shutil.which", return_value="/usr/local/bin/pico2wave"):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Return config."""
    return {}


@pytest.mark.parametrize(
    ("config", "entity_id", "extra_service_data"),
    [
        ({}, "tts.pico_tts_en_us", {}),
        ({tts.CONF_LANG: "de-DE"}, "tts.pico_tts_de_de", {}),
        ({}, "tts.pico_tts_en_us", {tts.ATTR_LANGUAGE: "de-DE"}),
        ({tts.CONF_LANG: "en-GB"}, "tts.pico_tts_en_gb", {}),
        ({}, "tts.pico_tts_en_us", {tts.ATTR_LANGUAGE: "en-GB"}),
    ],
)
async def test_tts_service(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    service_calls: list[ServiceCall],
    setup_picotts: None,
    entity_id: str,
    extra_service_data: dict[str, Any],
) -> None:
    """Test tts speak service with various language configurations."""
    mock_result = MagicMock()
    mock_result.returncode = 0
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
            return_value=mock_result,
        ),
        patch(
            "homeassistant.components.picotts.tts.open",
            mock_open(read_data=get_empty_wav()),
        ),
        patch("homeassistant.components.picotts.tts.os.remove"),
    ):
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


async def test_get_tts_audio_subprocess_error(
    hass: HomeAssistant,
    setup_picotts: None,
) -> None:
    """Test get_tts_audio when subprocess returns non-zero exit code."""
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "pico2wave"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass, "Hello world", "tts.pico_tts_en_us", "en-US"
            ),
        )

    assert exc_info.value.translation_key == "returncode_error"
    assert exc_info.value.translation_placeholders == {"returncode": "1"}


async def test_get_tts_audio_file_read_error(
    hass: HomeAssistant,
    setup_picotts: None,
) -> None:
    """Test get_tts_audio when reading the wav file fails."""
    with (
        patch(
            "homeassistant.components.picotts.tts.subprocess.run",
        ),
        patch(
            "homeassistant.components.picotts.tts.open",
            side_effect=FileNotFoundError("No such file"),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass, "Hello world", "tts.pico_tts_en_us", "en-US"
            ),
        )

    assert exc_info.value.translation_key == "file_read_error"
