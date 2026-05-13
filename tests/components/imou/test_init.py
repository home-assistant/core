"""Tests for the Imou init."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.imou.coordinator import ImouDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .util import create_mock_api_client, create_mock_device_manager

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    imou_integration: AsyncMock,
) -> None:
    """Test loading and unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_failed_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """First coordinator refresh failure surfaces as setup error."""
    mock_config_entry.add_to_hass(hass)
    mock_dm = create_mock_device_manager()
    mock_dm.async_get_devices = AsyncMock(return_value=[])

    with (
        patch(
            "homeassistant.components.imou.ImouOpenApiClient",
            return_value=create_mock_api_client(),
        ),
        patch(
            "homeassistant.components.imou.ImouHaDeviceManager",
            return_value=mock_dm,
        ),
        patch.object(
            ImouDataUpdateCoordinator,
            "async_config_entry_first_refresh",
            AsyncMock(side_effect=RuntimeError("Setup failed")),
        ),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
