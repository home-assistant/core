"""Tests helpers."""

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from google.cloud.texttospeech_v1.types import cloud_tts
import pytest

from homeassistant.components.google_cloud.const import (
    CONF_SERVICE_ACCOUNT_INFO,
    DOMAIN,
)

from tests.common import MockConfigEntry

VALID_SERVICE_ACCOUNT_INFO = {
    "type": "service_account",
    "project_id": "my project id",
    "private_key_id": "my private key if",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIICdwIBADANBgkqhkiG9w0BAQEFAASCAmEwggJdAgEAAoGBAKYscIlwm7soDsHAz6L6YvUkCvkrX19rS6yeYOmovvhoK5WeYGWUsd8V72zmsyHB7XO94YgJVjvxfzn5K8bLePjFzwoSJjZvhBJ/ZQ05d8VmbvgyWUoPdG9oEa4fZ/lCYrXoaFdTot2xcJvrb/ZuiRl4s4eZpNeFYvVK/Am7UeFPAgMBAAECgYAUetOfzLYUudofvPCaKHu7tKZ5kQPfEa0w6BAPnBF1Mfl1JiDBRDMryFtKs6AOIAVwx00dY/Ex0BCbB3+Cr58H7t4NaPTJxCpmR09pK7o17B7xAdQv8+SynFNud9/5vQ5AEXMOLNwKiU7wpXT6Z7ZIibUBOR7ewsWgsHCDpN1iqQJBAOMODPTPSiQMwRAUHIc6GPleFSJnIz2PAoG3JOG9KFAL6RtIc19lob2ZXdbQdzKtjSkWo+O5W20WDNAl1k32h6MCQQC7W4ZCIY67mPbL6CxXfHjpSGF4Dr9VWJ7ZrKHr6XUoOIcEvsn/pHvWonjMdy93rQMSfOE8BKd/I1+GHRmNVgplAkAnSo4paxmsZVyfeKt7Jy2dMY+8tVZe17maUuQaAE7Sk00SgJYegwrbMYgQnWCTL39HBfj0dmYA2Zj8CCAuu6O7AkEAryFiYjaUAO9+4iNoL27+ZrFtypeeadyov7gKs0ZKaQpNyzW8A+Zwi7TbTeSqzic/E+z/bOa82q7p/6b7141xsQJBANCAcIwMcVb6KVCHlQbOtKspo5Eh4ZQi8bGl+IcwbQ6JSxeTx915IfAldgbuU047wOB04dYCFB2yLDiUGVXTifU=\n-----END PRIVATE KEY-----\n",
    "client_email": "my client email",
    "client_id": "my client id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/service-account",
    "universe_domain": "googleapis.com",
}


@pytest.fixture
def create_google_credentials_json(tmp_path: Path) -> str:
    """Create googlecredentials.json."""
    file_path = tmp_path / "googlecredentials.json"
    with open(file_path, "w", encoding="utf8") as f:
        json.dump(VALID_SERVICE_ACCOUNT_INFO, f)
    return str(file_path)


@pytest.fixture
def create_invalid_google_credentials_json(create_google_credentials_json: str) -> str:
    """Create invalid googlecredentials.json."""
    invalid_service_account_info = VALID_SERVICE_ACCOUNT_INFO.copy()
    invalid_service_account_info.pop("client_email")
    with open(create_google_credentials_json, "w", encoding="utf8") as f:
        json.dump(invalid_service_account_info, f)
    return create_google_credentials_json


@pytest.fixture
def mock_process_uploaded_file(
    create_google_credentials_json: str,
) -> Generator[MagicMock]:
    """Mock upload certificate files."""
    ctx_mock = MagicMock()
    ctx_mock.__enter__.return_value = Path(create_google_credentials_json)
    with patch(
        "homeassistant.components.google_cloud.config_flow.process_uploaded_file",
        return_value=ctx_mock,
    ) as mock_upload:
        yield mock_upload


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="my Google Cloud title",
        domain=DOMAIN,
        data={CONF_SERVICE_ACCOUNT_INFO: VALID_SERVICE_ACCOUNT_INFO},
    )


@pytest.fixture
def mock_api_tts() -> AsyncMock:
    """Return a mocked TTS client."""
    mock_client = AsyncMock()
    mock_client.list_voices.return_value = cloud_tts.ListVoicesResponse(
        voices=[
            cloud_tts.Voice(language_codes=["en-US"], name="en-US-Standard-A"),
            cloud_tts.Voice(language_codes=["en-US"], name="en-US-Standard-B"),
            cloud_tts.Voice(language_codes=["el-GR"], name="el-GR-Standard-A"),
        ]
    )
    return mock_client


@pytest.fixture
def mock_api_tts_from_service_account_info(
    mock_api_tts: AsyncMock,
) -> Generator[AsyncMock]:
    """Return a mocked TTS client created with from_service_account_info."""
    with (
        patch(
            "google.cloud.texttospeech.TextToSpeechAsyncClient.from_service_account_info",
            return_value=mock_api_tts,
        ),
    ):
        yield mock_api_tts


@pytest.fixture
def mock_api_tts_from_service_account_file(
    mock_api_tts: AsyncMock,
) -> Generator[AsyncMock]:
    """Return a mocked TTS client created with from_service_account_file."""
    with (
        patch(
            "google.cloud.texttospeech.TextToSpeechAsyncClient.from_service_account_file",
            return_value=mock_api_tts,
        ),
    ):
        yield mock_api_tts


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.google_cloud.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
