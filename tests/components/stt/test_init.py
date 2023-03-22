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
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import mock_platform
from tests.typing import ClientSessionGenerator


class MockProvider(Provider):
    """Mock provider."""

    fail_process_audio = False

    def __init__(self) -> None:
        """Init test provider."""
        self.calls = []

    @property
    def supported_languages(self) -> list[str]:
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
def mock_provider() -> MockProvider:
    """Test provider fixture."""
    return MockProvider()


@pytest.fixture(autouse=True)
async def mock_setup(hass: HomeAssistant, mock_provider: MockProvider) -> None:
    """Set up a test provider."""
    mock_platform(
        hass, "test.stt", Mock(async_get_engine=AsyncMock(return_value=mock_provider))
    )
    assert await async_setup_component(hass, "stt", {"stt": {"platform": "test"}})


async def test_get_provider_info(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
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


async def test_get_non_existing_provider_info(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test streaming to engine that doesn't exist."""
    client = await hass_client()
    response = await client.get("/api/stt/not_exist")
    assert response.status == HTTPStatus.NOT_FOUND


async def test_stream_audio(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test streaming audio and getting response."""
    client = await hass_client()
    response = await client.post(
        "/api/stt/test",
        headers={
            "X-Speech-Content": (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1;"
                " language=en"
            )
        },
    )
    assert response.status == HTTPStatus.OK
    assert await response.json() == {"text": "test", "result": "success"}


@pytest.mark.parametrize(
    ("header", "status", "error"),
    (
        (None, 400, "Missing X-Speech-Content header"),
        (
            (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=100;"
                " language=en"
            ),
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
async def test_metadata_errors(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    header: str | None,
    status: int,
    error: str,
) -> None:
    """Test metadata errors."""
    client = await hass_client()
    headers: dict[str, str] = {}
    if header:
        headers["X-Speech-Content"] = header

    response = await client.post("/api/stt/test", headers=headers)
    assert response.status == status
    assert await response.text() == error


async def test_get_provider(hass: HomeAssistant, mock_provider: MockProvider) -> None:
    """Test we can get STT providers."""
    assert mock_provider == async_get_provider(hass, "test")
