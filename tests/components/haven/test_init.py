"""Test setup for the HAVEN IAQ integration."""

from unittest.mock import ANY, AsyncMock, MagicMock

from haveniaq import (
    HavenApiError,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_unload_ram_entry(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_haven_client_class: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up and unloading an air-quality entry."""
    await setup_integration(hass, mock_config_entry)

    mock_haven_client_class.assert_called_once_with(
        mock_config_entry.data["host"],
        session=ANY,
    )
    mock_haven_client.get_sensors.assert_awaited_once()
    mock_haven_client.get_status.assert_not_awaited()
    mock_haven_client.get_controller.assert_not_awaited()
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "error",
    [
        HavenUnsupportedApiVersionError("Unsupported API version"),
        HavenUnsupportedProductError("Unsupported product"),
    ],
)
async def test_setup_unsupported_device(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """Test unsupported devices fail setup without retrying."""
    mock_haven_client.get_info.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_retry(
    hass: HomeAssistant,
    mock_haven_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test retrying setup after a transient connection failure."""
    mock_haven_client.get_info.side_effect = HavenApiError("Unable to connect")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
