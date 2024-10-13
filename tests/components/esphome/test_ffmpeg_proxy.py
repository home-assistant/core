"""Tests for ffmpeg proxy view."""

from http import HTTPStatus
import io
import tempfile
from unittest.mock import patch
from urllib.request import pathname2url
import wave

import mutagen

from homeassistant.components import esphome
from homeassistant.components.esphome.ffmpeg_proxy import async_create_proxy_url
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


async def test_async_create_proxy_url(hass: HomeAssistant) -> None:
    """Test that async_create_proxy_url returns the correct format."""
    assert await async_setup_component(hass, "esphome", {})

    device_id = "test-device"
    convert_id = "test-id"
    media_format = "flac"
    media_url = "http://127.0.0.1/test.mp3"
    proxy_url = f"/api/esphome/ffmpeg_proxy/{device_id}/{convert_id}.{media_format}"

    with patch(
        "homeassistant.components.esphome.ffmpeg_proxy.secrets.token_urlsafe",
        return_value=convert_id,
    ):
        assert (
            async_create_proxy_url(hass, device_id, media_url, media_format)
            == proxy_url
        )


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
        convert_id = "test-id"
        url = f"/api/esphome/ffmpeg_proxy/{device_id}/{convert_id}.mp3"

        # Should fail because we haven't allowed the URL yet
        req = await client.get(url)
        assert req.status == HTTPStatus.NOT_FOUND

        # Allow the URL
        with patch(
            "homeassistant.components.esphome.ffmpeg_proxy.secrets.token_urlsafe",
            return_value=convert_id,
        ):
            assert (
                async_create_proxy_url(
                    hass, device_id, wav_url, media_format="mp3", rate=22050, channels=2
                )
                == url
            )

        # Requesting the wrong media format should fail
        wrong_url = f"/api/esphome/ffmpeg_proxy/{device_id}/{convert_id}.flac"
        req = await client.get(wrong_url)
        assert req.status == HTTPStatus.BAD_REQUEST

        # Correct URL
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


async def test_ffmpeg_file_doesnt_exist(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test ffmpeg conversion with a file that doesn't exist."""
    device_id = "1234"

    await async_setup_component(hass, esphome.DOMAIN, {esphome.DOMAIN: {}})
    client = await hass_client()

    # Try to convert a file that doesn't exist
    url = async_create_proxy_url(hass, device_id, "missing-file", media_format="mp3")
    req = await client.get(url)

    # The HTTP status is OK because the ffmpeg process started, but no data is
    # returned.
    assert req.status == HTTPStatus.OK
    mp3_data = await req.content.read()
    assert not mp3_data


async def test_lingering_process(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that a new request stops the old ffmpeg process."""
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
        url1 = async_create_proxy_url(
            hass,
            device_id,
            wav_url,
            media_format="wav",
            rate=22050,
            channels=2,
            width=2,
        )

        # First request will start ffmpeg
        req1 = await client.get(url1)
        assert req1.status == HTTPStatus.OK

        # Only read part of the data
        await req1.content.readexactly(100)

        # Allow another URL
        url2 = async_create_proxy_url(
            hass,
            device_id,
            wav_url,
            media_format="wav",
            rate=22050,
            channels=2,
            width=2,
        )

        req2 = await client.get(url2)
        assert req2.status == HTTPStatus.OK

        wav_data = await req2.content.read()

    # All of the data should be there because this is a new ffmpeg process
    with io.BytesIO(wav_data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        # We can't use getnframes() here because the WAV header will be incorrect.
        # WAV encoders usually go back and update the WAV header after all of
        # the frames are written, but ffmpeg can't do that because we're
        # streaming the data.
        # So instead, we just read and count frames until we run out.
        num_frames = 0
        while chunk := wav_file.readframes(1024):
            num_frames += len(chunk) // (2 * 2)  # 2 channels, 16-bit samples

        assert num_frames == 22050  # 1s


async def test_request_same_url_multiple_times(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that the ffmpeg process is restarted if the same URL is requested multiple times."""
    device_id = "1234"

    await async_setup_component(hass, esphome.DOMAIN, {esphome.DOMAIN: {}})
    client = await hass_client()

    with tempfile.NamedTemporaryFile(mode="wb+", suffix=".wav") as temp_file:
        with wave.open(temp_file.name, "wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(bytes(16000 * 2 * 10))  # 10s

        temp_file.seek(0)
        wav_url = pathname2url(temp_file.name)
        url = async_create_proxy_url(
            hass,
            device_id,
            wav_url,
            media_format="wav",
            rate=22050,
            channels=2,
            width=2,
        )

        # First request will start ffmpeg
        req1 = await client.get(url)
        assert req1.status == HTTPStatus.OK

        # Only read part of the data
        await req1.content.readexactly(100)

        # Second request should restart ffmpeg
        req2 = await client.get(url)
        assert req2.status == HTTPStatus.OK

        wav_data = await req2.content.read()

    # All of the data should be there because this is a new ffmpeg process
    with io.BytesIO(wav_data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        num_frames = 0
        while chunk := wav_file.readframes(1024):
            num_frames += len(chunk) // (2 * 2)  # 2 channels, 16-bit samples

        assert num_frames == 22050 * 10  # 10s
