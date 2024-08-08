"""Unit tests for ZHA backup platform."""

from unittest.mock import AsyncMock, patch

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


@patch("homeassistant.components.zha.backup.get_zha_gateway", side_effect=ValueError())
async def test_pre_backup_no_gateway(hass: HomeAssistant, setup_zha) -> None:
    """Test graceful backup failure when no gateway exists."""
    await setup_zha()
    await async_pre_backup(hass)


async def test_post_backup(hass: HomeAssistant, setup_zha) -> None:
    """Test no-op `async_post_backup`."""
    await setup_zha()
    await async_post_backup(hass)
