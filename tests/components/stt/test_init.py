"""Test STT component setup."""
from asyncio import StreamReader
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    Provider,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
    async_get_provider,
)
from homeassistant.setup import async_setup_component

from tests.common import mock_platform


class TestProvider(Provider):
    """Test provider."""

    fail_process_audio = False

    def __init__(self) -> None:
        """Init test provider."""
        self.calls = []

    @property
    def supported_languages(self):
        """Return a list of supported languages."""
        return ["en"]

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV, AudioFormats.OGG]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM, AudioCodecs.OPUS]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream: StreamReader
    ) -> SpeechResult:
        """Process an audio stream."""
        self.calls.append((metadata, stream))
        if self.fail_process_audio:
            return SpeechResult(None, SpeechResultState.ERROR)

        return SpeechResult("test", SpeechResultState.SUCCESS)


@pytest.fixture
def test_provider():
    """Test provider fixture."""
    return TestProvider()


@pytest.fixture(autouse=True)
async def mock_setup(hass, test_provider):
    """Set up a test provider."""
    mock_platform(
        hass, "test.stt", Mock(async_get_engine=AsyncMock(return_value=test_provider))
    )
    assert await async_setup_component(hass, "stt", {"stt": {"platform": "test"}})


async def test_get_provider_info(hass, hass_client):
    """Test engine that doesn't exist."""
    client = await hass_client()
    response = await client.get("/api/stt/test")
    assert response.status == HTTPStatus.OK
    assert await response.json() == {
        "languages": ["en"],
        "formats": ["wav", "ogg"],
        "codecs": ["pcm", "opus"],
        "sample_rates": [16000],
        "bit_rates": [16],
        "channels": [1],
    }


async def test_get_non_existing_provider_info(hass, hass_client):
    """Test streaming to engine that doesn't exist."""
    client = await hass_client()
    response = await client.get("/api/stt/not_exist")
    assert response.status == HTTPStatus.NOT_FOUND


async def test_stream_audio(hass, hass_client):
    """Test streaming audio and getting response."""
    client = await hass_client()
    response = await client.post(
        "/api/stt/test",
        headers={
            "X-Speech-Content": "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1; language=en"
        },
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == {"text": "test", "result": "success"}


@pytest.mark.parametrize(
    "header,status,error",
    (
        (None, 400, "Missing X-Speech-Content header"),
        (
            "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=100; language=en",
            400,
            "100 is not a valid AudioChannels",
        ),
        (
            "format=wav; codec=pcm; sample_rate=16000",
            400,
            "Missing language in X-Speech-Content header",
        ),
    ),
)
async def test_metadata_errors(hass, hass_client, header, status, error):
    """Test metadata errors."""
    client = await hass_client()
    headers = {}
    if header:
        headers["X-Speech-Content"] = header

    response = await client.post("/api/stt/test", headers=headers)
    assert response.status == status
    assert await response.text() == error


async def test_get_provider(hass, test_provider):
    """Test we can get STT providers."""
    assert test_provider == async_get_provider(hass, "test")
