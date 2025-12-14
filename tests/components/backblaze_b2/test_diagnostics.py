"""Test Backblaze B2 diagnostics."""

from unittest.mock import Mock, patch

from homeassistant.components.backblaze_b2.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_diagnostics_basic(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test basic diagnostics data collection."""
    await setup_integration(hass, mock_config_entry)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "entry_data" in result
    assert "entry_options" in result
    assert "bucket_info" in result
    assert "account_info" in result

    # Check that sensitive data is redacted
    assert mock_config_entry.data["key_id"] not in str(result["entry_data"])
    assert mock_config_entry.data["application_key"] not in str(result["entry_data"])


async def test_diagnostics_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test diagnostics handles errors gracefully."""
    mock_config_entry.runtime_data = None
    mock_config_entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert "bucket_info" in result
    assert "account_info" in result


async def test_diagnostics_bucket_data_redaction(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test diagnostics redacts bucket-specific sensitive data."""
    await setup_integration(hass, mock_config_entry)

    mock_bucket = Mock()
    mock_bucket.name = "test-bucket"
    mock_bucket.id_ = "bucket_id_123"
    mock_bucket.type_ = "allPrivate"
    mock_bucket.cors_rules = []
    mock_bucket.lifecycle_rules = []
    mock_bucket.revision = 1

    mock_api = Mock()
    mock_account_info = Mock()
    mock_account_info.get_account_id.return_value = "account123"
    mock_account_info.get_api_url.return_value = "https://api.backblazeb2.com"
    mock_account_info.get_download_url.return_value = "https://f001.backblazeb2.com"
    mock_account_info.get_minimum_part_size.return_value = 5000000
    mock_account_info.get_allowed.return_value = {
        "capabilities": ["writeFiles", "listFiles", "readFiles"],
        "bucketId": "test_bucket_id_123",
        "bucketName": "restricted_bucket",
        "namePrefix": "restricted/path/",
    }

    mock_bucket.api = mock_api
    mock_api.account_info = mock_account_info

    with patch.object(mock_config_entry, "runtime_data", mock_bucket):
        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    account_data = result["account_info"]

    assert account_data["allowed"]["capabilities"] == [
        "writeFiles",
        "listFiles",
        "readFiles",
    ]
    assert account_data["allowed"]["bucketId"] == "**REDACTED**"
    assert account_data["allowed"]["bucketName"] == "**REDACTED**"
    assert account_data["allowed"]["namePrefix"] == "**REDACTED**"
