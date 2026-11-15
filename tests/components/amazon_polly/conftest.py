"""Common fixtures for the Amazon Polly tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.amazon_polly.const import (
    CONF_ACCESS_KEY_ID,
    CONF_REGION,
    CONF_SECRET_ACCESS_KEY,
    DOMAIN,
)

ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE"
SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
REGION = "us-east-1"
UNIQUE_ID = f"{ACCESS_KEY_ID}_{REGION}"

ENTRY_DATA = {
    CONF_REGION: REGION,
    CONF_ACCESS_KEY_ID: ACCESS_KEY_ID,
    CONF_SECRET_ACCESS_KEY: SECRET_ACCESS_KEY,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.amazon_polly.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return an Amazon Polly config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JPOLLYENTRY0000000000000",
        title=f"Amazon Polly ({REGION})",
        data=ENTRY_DATA,
        unique_id=UNIQUE_ID,
    )


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
