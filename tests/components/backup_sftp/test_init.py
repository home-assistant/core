"""Tests for SFTP Backup Location."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.backup_sftp import SFTPConfigEntryData
from homeassistant.components.backup_sftp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import USER_INPUT

from tests.common import MockConfigEntry

type ComponentSetup = Callable[[], Awaitable[None]]


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
@patch("homeassistant.components.backup_sftp.client.connect", new_callable=AsyncMock)
async def test_setup_and_unload(
    mock_connect: AsyncMock,
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    ssh_objects: tuple[AsyncMock, AsyncMock],
) -> None:
    """Test successful setup and unload."""
    mock_ssh, mock_sftp = ssh_objects
    mock_connect.return_value = mock_ssh

    # Mock SFTP methods
    mock_sftp.chdir = AsyncMock()
    mock_sftp.listdir = AsyncMock(return_value=[])

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
    async_cm_mock: AsyncMock,
    setup_integration: Callable,
) -> None:
    """Test setup error."""
    backup_agent_client.return_value = async_cm_mock
    async_cm_mock.list_backup_location.return_value = None

    await setup_integration()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR


@patch(
    "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
    MagicMock(),
)
@patch("homeassistant.components.backup_sftp.client.connect")
async def test_setup_error_reauth(
    mock_connect: AsyncMock,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test reauth trigger on `BackupAgentClient` failure.

    This test is not using `setup_integration` fixture because it already mocked `asyncssh` to work fine.
    """
    mock_connect.side_effect = OSError("Error message")

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    assert entries[0].state is ConfigEntryState.NOT_LOADED


async def test_config_entry_data_password_hidden() -> None:
    """Test hiding password in `SFTPConfigEntryData` string representation."""
    entry_data = SFTPConfigEntryData(**USER_INPUT)
    assert "password=" not in str(entry_data)
