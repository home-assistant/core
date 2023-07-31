"""Unit tests for ZHA backup platform."""
from unittest.mock import AsyncMock, patch

from homeassistant.components.zha.backup import async_post_backup, async_pre_backup
from homeassistant.core import HomeAssistant


async def test_pre_backup(hass: HomeAssistant, setup_zha) -> None:
    """Test backup creation when `async_pre_backup` is called."""
    with patch("zigpy.backups.BackupManager.create_backup", AsyncMock()) as backup_mock:
        await setup_zha()
        await async_pre_backup(hass)

    backup_mock.assert_called_once_with(load_devices=True)


async def test_post_backup(hass: HomeAssistant, setup_zha) -> None:
    """Test no-op `async_post_backup`."""
    await setup_zha()
    await async_post_backup(hass)
