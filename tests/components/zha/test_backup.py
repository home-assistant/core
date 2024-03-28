"""Unit tests for ZHA backup platform."""

from unittest.mock import AsyncMock

from zigpy.application import ControllerApplication

from homeassistant.components.zha.backup import async_post_backup, async_pre_backup
from homeassistant.core import HomeAssistant


async def test_pre_backup(
    hass: HomeAssistant, zigpy_app_controller: ControllerApplication, setup_zha
) -> None:
    """Test backup creation when `async_pre_backup` is called."""
    await setup_zha()

    zigpy_app_controller.backups.create_backup = AsyncMock()
    await async_pre_backup(hass)

    zigpy_app_controller.backups.create_backup.assert_called_once_with(
        load_devices=True
    )


async def test_post_backup(hass: HomeAssistant, setup_zha) -> None:
    """Test no-op `async_post_backup`."""
    await setup_zha()
    await async_post_backup(hass)
