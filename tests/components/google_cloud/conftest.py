"""Tests helpers."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

from google.cloud.texttospeech_v1.types import cloud_tts
import pytest

from homeassistant.components.google_cloud.const import CONF_KEY_FILE, DOMAIN
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


@pytest.fixture
def create_google_credentials_json(tmp_path: Path) -> str:
    """Create googlecredentials.json."""
    file_path = tmp_path / "googlecredentials.json"
    with open(file_path, "w", encoding="utf8") as f:
        f.write("test")
    return str(file_path)


@pytest.fixture
def mock_config_entry(create_google_credentials_json: str) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="my Google Cloud title",
        domain=DOMAIN,
        data={CONF_KEY_FILE: create_google_credentials_json},
        state=ConfigEntryState.NOT_LOADED,
    )


@pytest.fixture
def mock_api_tts():
    """Return a mocked TTS client."""
    mock_client = AsyncMock()
    mock_client.list_voices.return_value = cloud_tts.ListVoicesResponse(
        voices=[
            cloud_tts.Voice(language_codes=["en-US"], name="en-US-Standard-A"),
            cloud_tts.Voice(language_codes=["en-US"], name="en-US-Standard-B"),
            cloud_tts.Voice(language_codes=["el-GR"], name="el-GR-Standard-A"),
        ]
    )
    with patch(
        "google.cloud.texttospeech.TextToSpeechAsyncClient.from_service_account_file",
        return_value=mock_client,
    ):
        yield
