"""Test Backblaze diagnostics."""

from unittest.mock import patch

from homeassistant.components.backblaze.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_diagnostics(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test diagnostics data."""
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
    # Create entry with broken runtime_data to trigger error paths
    mock_config_entry.runtime_data = None
    mock_config_entry.add_to_hass(hass)

    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Should still return result with error info
    assert "bucket_info" in result
    assert "account_info" in result


async def test_diagnostics_bucket_data_redaction(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test diagnostics redacts bucket-specific data when bucketId is present."""
    await setup_integration(hass, mock_config_entry)

    # Mock get_allowed to return data with bucketId to trigger redaction
    with patch.object(
        mock_config_entry.runtime_data.api.account_info,
        "get_allowed",
        return_value={
            "capabilities": ["writeFiles", "listFiles", "readFiles"],
            "bucketId": "test_bucket_id_123",
            "bucketName": "restricted_bucket",
            "namePrefix": "restricted/path/",
        },
    ):
        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Check that bucket-specific sensitive data was redacted
    assert "account_info" in result
    account_data = result["account_info"]

    # Capabilities should be preserved
    assert account_data["allowed"]["capabilities"] == [
        "writeFiles",
        "listFiles",
        "readFiles",
    ]

    # But bucket-specific data should be redacted
    assert account_data["allowed"]["bucketId"] == "**REDACTED**"
    assert account_data["allowed"]["bucketName"] == "**REDACTED**"
    assert account_data["allowed"]["namePrefix"] == "**REDACTED**"
