"""Tests for ALLNET async_setup_entry and async_unload_entry."""

from unittest.mock import AsyncMock, MagicMock, patch

from allnet.exceptions import AllnetAuthenticationError, AllnetConnectionError
import pytest

from homeassistant.components.allnet.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_UNIQUE_ID


@pytest.mark.asyncio
async def test_setup_entry_success(hass: HomeAssistant, setup_integration) -> None:
    """Test that async_setup_entry succeeds with a valid mock client."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is not None
    assert entry.runtime_data.client is not None
    assert entry.runtime_data.coordinator is not None
    assert entry.runtime_data.ha_device_info is not None


@pytest.mark.asyncio
async def test_setup_entry_auth_failed(
    hass: HomeAssistant, config_entry, mock_allnet_client
) -> None:
    """Test that async_setup_entry raises ConfigEntryAuthFailed on auth error."""
    mock_allnet_client.async_get_device_info = AsyncMock(
        side_effect=AllnetAuthenticationError("401")
    )
    mock_session = MagicMock()

    with (
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
        patch(
            "homeassistant.components.allnet.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        await hass.config_entries.async_add(config_entry)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.asyncio
async def test_setup_entry_not_ready(
    hass: HomeAssistant, config_entry, mock_allnet_client
) -> None:
    """Test that async_setup_entry raises ConfigEntryNotReady on connection error."""
    mock_allnet_client.async_get_device_info = AsyncMock(
        side_effect=AllnetConnectionError("unreachable")
    )
    mock_session = MagicMock()

    with (
        patch(
            "homeassistant.components.allnet.AllnetClient",
            return_value=mock_allnet_client,
        ),
        patch(
            "homeassistant.components.allnet.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        await hass.config_entries.async_add(config_entry)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.asyncio
async def test_unload_entry(hass: HomeAssistant, setup_integration) -> None:
    """Test that async_unload_entry unloads all platforms."""
    entry = setup_integration
    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert result is True
    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.asyncio
async def test_setup_creates_device(hass: HomeAssistant, setup_integration) -> None:
    """Test that setup registers a device in the device registry."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, TEST_UNIQUE_ID)})

    assert device is not None
    assert device.manufacturer == "ALLNET"
    assert device.model == "ALL3500"
    assert device.sw_version == "1.2.3"
    assert device.name == "ALLNET Test Device"
