"""Tests for the yolink integration."""

from unittest.mock import AsyncMock, patch

import pytest
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.components.yolink import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager", "mock_yolink_home")
async def test_device_remove_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we can only remove a device that no longer exists."""

    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale_device_id")},
    )
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    assert len(device_entries) == 1
    device_entry = device_entries[0]
    assert device_entry.identifiers == {(DOMAIN, "stale_device_id")}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 0


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager", "mock_yolink_home")
async def test_oauth_implementation_not_available(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that an unavailable OAuth implementation raises ConfigEntryNotReady."""
    assert await async_setup_component(hass, "cloud", {})

    with patch(
        "homeassistant.components.yolink.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials", "mock_auth_manager", "mock_yolink_home")
async def test_oauth_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test OAuth config entry setup and unload."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_yolink_home")
async def test_uac_setup_and_unload(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
) -> None:
    """Test UAC config entry setup and unload."""
    with patch("homeassistant.components.yolink.api.UACAuth", autospec=True):
        assert await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_uac_config_entry.entry_id)
    assert mock_uac_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_yolink_home")
async def test_uac_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
) -> None:
    """Test UAC setup entry with auth failure triggers reauth."""
    mock_yolink_home.return_value.async_setup.side_effect = YoLinkAuthFailError(
        "000103", "Invalid credentials"
    )

    with patch("homeassistant.components.yolink.api.UACAuth", autospec=True):
        await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.usefixtures("mock_yolink_home")
async def test_uac_setup_entry_connection_failure(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
) -> None:
    """Test UAC setup entry with connection failure retries."""
    mock_yolink_home.return_value.async_setup.side_effect = YoLinkClientError(
        "000201", "Connection failed"
    )

    with patch("homeassistant.components.yolink.api.UACAuth", autospec=True):
        await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_yolink_home")
async def test_uac_setup_entry_timeout(
    hass: HomeAssistant,
    mock_uac_config_entry: MockConfigEntry,
    mock_yolink_home: AsyncMock,
) -> None:
    """Test UAC setup entry with timeout retries."""
    mock_yolink_home.return_value.async_setup.side_effect = TimeoutError()

    with patch("homeassistant.components.yolink.api.UACAuth", autospec=True):
        await hass.config_entries.async_setup(mock_uac_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_uac_config_entry.state is ConfigEntryState.SETUP_RETRY
