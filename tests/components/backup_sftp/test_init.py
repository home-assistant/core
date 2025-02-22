"""Tests for Google Drive."""

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.backup_sftp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

type ComponentSetup = Callable[[], Awaitable[None]]


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    async def func() -> None:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return func


@patch("homeassistant.components.backup_sftp.BackupAgentClient")
async def test_setup_success(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    async_cm_mock: AsyncMock,
) -> None:
    """Test successful setup and unload."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.list_backup_location.return_value = []
    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert entries[0].state is ConfigEntryState.NOT_LOADED


@patch("homeassistant.components.backup_sftp.BackupAgentClient")
async def test_setup_error(
    backup_agent_client: MagicMock,
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    async_cm_mock: AsyncMock,
) -> None:
    """Test setup error."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.list_backup_location.return_value = None

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY
