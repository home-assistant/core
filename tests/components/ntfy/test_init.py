"""Tests for the ntfy integration."""

from unittest.mock import AsyncMock, patch

from aiontfy.exceptions import (
    NtfyConnectionError,
    NtfyHTTPError,
    NtfyTimeoutError,
    NtfyUnauthorizedAuthenticationError,
)
import pytest

from homeassistant.components.ntfy.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_aiontfy")
async def test_entry_setup_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_aiontfy")
async def test_topic_device_via_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test topic device is linked to the account service device.

    The account service device is registered at setup so the topic device,
    which is created by the event/notify platforms, is always linked to it
    even when the sensor platform (which also creates the account device) is
    not loaded.
    """

    with patch("homeassistant.components.ntfy.PLATFORMS", [Platform.EVENT]):
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    subentry_id = next(iter(config_entry.subentries))
    account_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, config_entry.entry_id), config_entry.entry_id
    )
    topic_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{config_entry.entry_id}_{subentry_id}"), config_entry.entry_id
    )

    assert account_device is not None
    assert topic_device is not None
    assert topic_device.via_device_id == account_device.id


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (
            NtfyUnauthorizedAuthenticationError(
                40101,
                401,
                "unauthorized",
                "https://ntfy.sh/docs/publish/#authentication",
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (NtfyHTTPError(418001, 418, "I'm a teapot", ""), ConfigEntryState.SETUP_RETRY),
        (NtfyConnectionError, ConfigEntryState.SETUP_RETRY),
        (NtfyTimeoutError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test config entry not ready."""

    mock_aiontfy.account.side_effect = exception
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (
            NtfyUnauthorizedAuthenticationError(
                40101,
                401,
                "unauthorized",
                "https://ntfy.sh/docs/publish/#authentication",
            ),
            ConfigEntryState.SETUP_ERROR,
        ),
        (NtfyHTTPError(418001, 418, "I'm a teapot", ""), ConfigEntryState.SETUP_RETRY),
        (NtfyConnectionError, ConfigEntryState.SETUP_RETRY),
        (NtfyTimeoutError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_coordinator_update_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_aiontfy: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test config entry not ready from update failed in _async_update_data."""
    mock_aiontfy.account.side_effect = [None, exception]

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is state
