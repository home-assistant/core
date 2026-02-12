"""Test that the integration is initialized correctly."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gentex_homelink.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.helpers.device_registry as dr

from . import setup_integration, update_callback

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_provider: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device is registered correctly."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "TestDevice")},
    )
    assert device
    assert device == snapshot


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_reload_sync(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_provider: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that the config entry is reloaded when a requestSync request is sent."""
    await setup_integration(hass, mock_config_entry)

    with patch.object(hass.config_entries, "async_reload") as async_reload_mock:
        await update_callback(
            hass,
            mock_mqtt_provider,
            "requestSync",
            {},
        )

        async_reload_mock.assert_called_once_with(mock_config_entry.entry_id)


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mqtt_provider: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the entry can be loaded and unloaded."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
