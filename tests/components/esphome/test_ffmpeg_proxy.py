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
        url = f"/api/esphome/ffmpeg_proxy?url={wav_url}&format=mp3&rate=22050&channels=2&device_id={device_id}"

        # Should fail because we haven't allowed the URL yet
        req = await client.get(url)
        assert req.status == HTTPStatus.BAD_REQUEST

        # Allow the URL
        async_allow_proxy_url(hass, device_id, wav_url)

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
    missing_file = pathname2url("does-not-exist.wav")
    url = (
        f"/api/esphome/ffmpeg_proxy?url={missing_file}&format=mp3&device_id={device_id}"
    )
    async_allow_proxy_url(hass, device_id, missing_file)
    req = await client.get(url)

    # The HTTP status is OK because the ffmpeg process started, but no data is
    # returned.
    assert req.status == HTTPStatus.OK
    mp3_data = await req.content.read()
    assert not mp3_data


async def test_view_schema(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test proxy HTTP view schema."""
    device_id = "1234"

    await async_setup_component(hass, esphome.DOMAIN, {esphome.DOMAIN: {}})
    client = await hass_client()

    url = "/api/esphome/ffmpeg_proxy"

    with tempfile.NamedTemporaryFile(mode="wb+", suffix=".wav") as temp_file:
        with wave.open(temp_file.name, "wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(bytes(16000 * 2))  # 1s

        temp_file.seek(0)
        wav_url = pathname2url(temp_file.name)

        # Missing device id
        req = await client.get(url)
        assert req.status == HTTPStatus.BAD_REQUEST

        # Missing url
        url += f"?device_id={device_id}"
        req = await client.get(url)
        assert req.status == HTTPStatus.BAD_REQUEST

        # Missing format
        async_allow_proxy_url(hass, device_id, wav_url)
        url += f"&url={wav_url}"
        req = await client.get(url)
        assert req.status == HTTPStatus.BAD_REQUEST

        # Got everything
        url += "&format=mp3"
        req = await client.get(url)
        assert req.status == HTTPStatus.OK
