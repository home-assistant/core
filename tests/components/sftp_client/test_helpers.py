"""Test the SFTPClient setup."""

from unittest.mock import patch

from homeassistant.components.sftp_client.helpers import PermissionDenied
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""

    with patch(
        "homeassistant.components.sftp_client.helpers.connect",
        side_effect=PermissionDenied("Permission denied"),
    ):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
