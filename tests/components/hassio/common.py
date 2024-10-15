"""Provide common test tools for hassio."""

from __future__ import annotations

from collections.abc import Generator
import logging
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, patch

from homeassistant.components.hassio.addon_manager import AddonManager
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


def mock_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Return an AddonManager instance."""
    return AddonManager(hass, LOGGER, "Test", "test_addon")


def mock_discovery_info() -> Any:
    """Return the discovery info from the supervisor."""
    return DEFAULT


def mock_get_addon_discovery_info(discovery_info: Any) -> Generator[AsyncMock]:
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_discovery_info",
        return_value=discovery_info,
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info


def mock_addon_store_info() -> Generator[AsyncMock]:
    """Mock Supervisor add-on store info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_store_info"
    ) as addon_store_info:
        addon_store_info.return_value = {
            "available": False,
            "installed": None,
            "state": None,
            "version": "1.0.0",
        }
        yield addon_store_info


def mock_addon_info() -> Generator[AsyncMock]:
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_info",
    ) as addon_info:
        addon_info.return_value = {
            "available": False,
            "hostname": None,
            "options": {},
            "state": None,
            "update_available": False,
            "version": None,
        }
        yield addon_info


def mock_addon_not_installed(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on not installed."""
    addon_store_info.return_value["available"] = True
    return addon_info


def mock_addon_installed(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already installed but not running."""
    addon_store_info.return_value = {
        "available": True,
        "installed": "1.0.0",
        "state": "stopped",
        "version": "1.0.0",
    }
    addon_info.return_value["available"] = True
    addon_info.return_value["hostname"] = "core-test-addon"
    addon_info.return_value["state"] = "stopped"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


def mock_addon_running(addon_store_info: AsyncMock, addon_info: AsyncMock) -> AsyncMock:
    """Mock add-on already running."""
    addon_store_info.return_value = {
        "available": True,
        "installed": "1.0.0",
        "state": "started",
        "version": "1.0.0",
    }
    addon_info.return_value["available"] = True
    addon_info.return_value["hostname"] = "core-mosquitto"
    addon_info.return_value["state"] = "started"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


def mock_install_addon(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Generator[AsyncMock]:
    """Mock install add-on."""

    async def install_addon_side_effect(hass: HomeAssistant, slug: str) -> None:
        """Mock install add-on."""
        addon_store_info.return_value = {
            "available": True,
            "installed": "1.0.0",
            "state": "stopped",
            "version": "1.0.0",
        }
        addon_info.return_value["available"] = True
        addon_info.return_value["state"] = "stopped"
        addon_info.return_value["version"] = "1.0.0"

    with patch(
        "homeassistant.components.hassio.addon_manager.async_install_addon"
    ) as install_addon:
        install_addon.side_effect = install_addon_side_effect
        yield install_addon


def mock_start_addon() -> Generator[AsyncMock]:
    """Mock start add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_start_addon"
    ) as start_addon:
        yield start_addon


def mock_stop_addon() -> Generator[AsyncMock]:
    """Mock stop add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_stop_addon"
    ) as stop_addon:
        yield stop_addon


def mock_restart_addon() -> Generator[AsyncMock]:
    """Mock restart add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_restart_addon"
    ) as restart_addon:
        yield restart_addon


def mock_uninstall_addon() -> Generator[AsyncMock]:
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon


def mock_set_addon_options() -> Generator[AsyncMock]:
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_set_addon_options"
    ) as set_options:
        yield set_options


def mock_create_backup() -> Generator[AsyncMock]:
    """Mock create backup."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_create_backup"
    ) as create_backup:
        yield create_backup


def mock_update_addon() -> Generator[AsyncMock]:
    """Mock update add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_update_addon"
    ) as update_addon:
        yield update_addon
