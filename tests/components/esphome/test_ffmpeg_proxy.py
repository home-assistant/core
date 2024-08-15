"""Tests for ffmpeg proxy view."""

from http import HTTPStatus
import io
import tempfile
from urllib.request import pathname2url
import wave

import mutagen

from homeassistant.components import esphome
from homeassistant.components.esphome.ffmpeg_proxy import async_allow_proxy_url
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


async def test_proxy_view(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test proxy HTTP view for converting audio."""
    device_id = "1234"

    await async_setup_component(hass, esphome.DOMAIN, {esphome.DOMAIN: {}})
    client = await hass_client()

    with tempfile.NamedTemporaryFile(mode="wb+", suffix=".wav") as temp_file:
        with wave.open(temp_file.name, "wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(bytes(16000 * 2))  # 1s

        temp_file.seek(0)
        wav_url = pathname2url(temp_file.name)
        convert_id = "not-a-valid-id"
        url = f"/api/esphome/ffmpeg_proxy/{device_id}/{convert_id}.mp3"

        # Should fail because we haven't allowed the URL yet
        req = await client.get(url)
        assert req.status == HTTPStatus.BAD_REQUEST

        # Allow the URL
        convert_id = async_allow_proxy_url(
            hass, device_id, wav_url, media_format="mp3", rate=22050, channels=2
        )
        url = f"/api/esphome/ffmpeg_proxy/{device_id}/{convert_id}.mp3"

        req = await client.get(url)
        assert req.status == HTTPStatus.OK

        mp3_data = await req.content.read()

    # Verify conversion
    with io.BytesIO(mp3_data) as mp3_io:
        mp3_file = mutagen.File(mp3_io)
        assert mp3_file.info.sample_rate == 22050
        assert mp3_file.info.channels == 2

        # About a second, but not exact
        assert round(mp3_file.info.length, 0) == 1


async def test_ffmpeg_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test proxy HTTP view with an ffmpeg error."""
    device_id = "1234"

    await async_setup_component(hass, esphome.DOMAIN, {esphome.DOMAIN: {}})
    client = await hass_client()

    # Try to convert a file that doesn't exist
    convert_id = async_allow_proxy_url(
        hass, device_id, "missing-file", media_format="mp3"
    )
    url = f"/api/esphome/ffmpeg_proxy/{device_id}/{convert_id}.mp3"
    req = await client.get(url)

    # The HTTP status is OK because the ffmpeg process started, but no data is
    # returned.
    assert req.status == HTTPStatus.OK
    mp3_data = await req.content.read()
    assert not mp3_data
