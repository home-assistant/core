"""Tests for the Gatus integration setup and unload lifecycle."""

from unittest.mock import AsyncMock

from gatus_api import GatusClientError
import pytest

from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_gatus_client")
async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test standard successful setup and unload cycle of the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert isinstance(mock_config_entry.runtime_data, GatusDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_failure_retry(
    hass: HomeAssistant,
    mock_gatus_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an API connection failure during initial setup places the entry in retry state."""
    mock_gatus_client.get_endpoints_statuses.side_effect = GatusClientError(
        "Cannot connect to Gatus API during initial setup"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_gatus_client")
async def test_remove_stale_device_runtime(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gatus_client: AsyncMock,
) -> None:
    """Test that a device is removed at runtime when it is no longer returned by the Gatus API."""
    await setup_integration(hass, mock_config_entry)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={("gatus", f"{mock_config_entry.entry_id}_backend_service")}
    )
    assert device is not None

    mock_gatus_client.get_endpoints_statuses.return_value = []

    coordinator = mock_config_entry.runtime_data
    await coordinator.async_refresh()

    device = device_registry.async_get_device(
        identifiers={("gatus", f"{mock_config_entry.entry_id}_backend_service")}
    )
    assert device is None


@pytest.mark.usefixtures("mock_gatus_client")
async def test_remove_stale_device_on_startup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that stale devices in the registry are removed on startup."""
    mock_config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("gatus", f"{mock_config_entry.entry_id}_stale_service")},
        name="Stale Service",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get(stale_device.id) is None

    active_device = device_registry.async_get_device(
        identifiers={("gatus", f"{mock_config_entry.entry_id}_backend_service")}
    )
    assert active_device is not None
