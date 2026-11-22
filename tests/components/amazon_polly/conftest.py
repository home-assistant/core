"""Common fixtures for the Amazon Polly tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import load_json_object_fixture

from homeassistant.components.amazon_polly.const import DOMAIN


@pytest.fixture
def mock_audio_stream() -> MagicMock:
    """Return the audio stream Polly sends back."""
    stream = MagicMock()
    stream.__aenter__.return_value = stream
    stream.read = AsyncMock(return_value=b"polly-audio")
    return stream


@pytest.fixture
def mock_session() -> Generator[MagicMock]:
    """Mock the aiobotocore session."""
    with patch(
        "homeassistant.components.amazon_polly.helpers.AioSession", autospec=True
    ) as mock_session:
        yield mock_session


@pytest.fixture
def mock_polly_client(
    mock_session: MagicMock, mock_audio_stream: MagicMock
) -> AsyncMock:
    """Mock the aiobotocore Polly client."""
    client = AsyncMock()
    client.describe_voices.return_value = load_json_object_fixture(
        "describe_voices.json", DOMAIN
    )
    client.synthesize_speech.return_value = {
        "AudioStream": mock_audio_stream,
        "ContentType": "audio/mpeg",
    }
    mock_session.return_value.create_client.return_value.__aenter__.return_value = (
        client
    )
    return client
