"""Test the Nederlandse Spoorwegen integration init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.nederlandse_spoorwegen import (
    DOMAIN,
    NSRuntimeData,
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady


@pytest.fixture
def mock_nsapi():
    """Mock NSAPI client."""
    with patch("homeassistant.components.nederlandse_spoorwegen.NSAPI") as mock:
        nsapi = mock.return_value
        nsapi.get_stations.return_value = []
        yield nsapi


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.data = {CONF_API_KEY: "test_api_key"}
    entry.options = {}
    entry.runtime_data = NSRuntimeData(coordinator=MagicMock())
    entry.async_on_unload = MagicMock()
    entry.add_update_listener = MagicMock()
    return entry


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup registers services."""
    result = await async_setup(hass, {})

    assert result is True
    assert hass.services.has_service(DOMAIN, "add_route")
    assert hass.services.has_service(DOMAIN, "remove_route")


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry, mock_nsapi
) -> None:
    """Test successful setup of config entry."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.NSDataUpdateCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = mock_coordinator_class.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()
        mock_nsapi.get_stations.return_value = []  # Ensure get_stations is called

        with patch.object(
            hass.config_entries, "async_forward_entry_setups"
        ) as mock_forward:
            result = await async_setup_entry(hass, mock_config_entry)

            assert result is True
            mock_nsapi.get_stations.assert_not_called()  # Now not called directly in setup
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()
            mock_forward.assert_called_once()
            assert hasattr(mock_config_entry.runtime_data, "coordinator")


async def test_async_setup_entry_connection_error(
    hass: HomeAssistant, mock_config_entry, mock_nsapi
) -> None:
    """Test setup entry with connection error."""
    mock_nsapi.get_stations.side_effect = Exception("Connection failed")
    mock_config_entry.state = None  # Add missing attribute for test

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)


async def test_async_reload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test reloading config entry."""
    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        await async_reload_entry(hass, mock_config_entry)
        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_async_unload_entry(hass: HomeAssistant, mock_config_entry) -> None:
    """Test unloading config entry."""
    with patch.object(hass.config_entries, "async_unload_platforms") as mock_unload:
        mock_unload.return_value = True

        result = await async_unload_entry(hass, mock_config_entry)

        assert result is True
        mock_unload.assert_called_once()
