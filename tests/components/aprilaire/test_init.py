"""Tests for the Aprilaire integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from pyaprilaire.const import Attribute
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_MAC, setup_integration

from tests.common import MockConfigEntry


pytestmark = [
    pytest.mark.usefixtures("mock_aprilaire"),
]


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test setup when the device is not ready."""
    # Remove MAC to trigger not-ready
    base_coordinator_data.pop(Attribute.MAC_ADDRESS, None)
    mock_client.wait_for_response.return_value = {}

    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aprilaire.coordinator.pyaprilaire.client.AprilaireClient",
        return_value=mock_client,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
