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


def mock_get_addon_discovery_info(
    discovery_info: dict[str, Any], discovery_info_side_effect: Any | None
) -> Generator[AsyncMock]:
    """Mock get add-on discovery info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_discovery_info",
        side_effect=discovery_info_side_effect,
        return_value=discovery_info,
    ) as get_addon_discovery_info:
        yield get_addon_discovery_info


def mock_addon_store_info(
    addon_store_info_side_effect: Any | None,
) -> Generator[AsyncMock]:
    """Mock Supervisor add-on store info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_store_info",
        side_effect=addon_store_info_side_effect,
    ) as addon_store_info:
        addon_store_info.return_value = {
            "available": True,
            "installed": None,
            "state": None,
            "version": "1.0.0",
        }
        yield addon_store_info


def mock_addon_info(addon_info_side_effect: Any | None) -> Generator[AsyncMock]:
    """Mock Supervisor add-on info."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_get_addon_info",
        side_effect=addon_info_side_effect,
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
    addon_info.return_value["hostname"] = "core-test-addon"
    addon_info.return_value["state"] = "started"
    addon_info.return_value["version"] = "1.0.0"
    return addon_info


def mock_install_addon_side_effect(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the install add-on side effect."""

    async def install_addon(hass: HomeAssistant, slug):
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

    return install_addon


def mock_install_addon(install_addon_side_effect: Any | None) -> Generator[AsyncMock]:
    """Mock install add-on."""

    with patch(
        "homeassistant.components.hassio.addon_manager.async_install_addon",
        side_effect=install_addon_side_effect,
    ) as install_addon:
        yield install_addon


def mock_start_addon_side_effect(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the start add-on options side effect."""

    async def start_addon(hass: HomeAssistant, slug):
        """Mock start add-on."""
        addon_store_info.return_value = {
            "available": True,
            "installed": "1.0.0",
            "state": "started",
            "version": "1.0.0",
        }
        addon_info.return_value["available"] = True
        addon_info.return_value["state"] = "started"

    return start_addon


def mock_start_addon(start_addon_side_effect: Any | None) -> Generator[AsyncMock]:
    """Mock start add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_start_addon",
        side_effect=start_addon_side_effect,
    ) as start_addon:
        yield start_addon


def mock_stop_addon() -> Generator[AsyncMock]:
    """Mock stop add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_stop_addon"
    ) as stop_addon:
        yield stop_addon


def mock_restart_addon(restart_addon_side_effect: Any | None) -> Generator[AsyncMock]:
    """Mock restart add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_restart_addon",
        side_effect=restart_addon_side_effect,
    ) as restart_addon:
        yield restart_addon


def mock_uninstall_addon() -> Generator[AsyncMock]:
    """Mock uninstall add-on."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_uninstall_addon"
    ) as uninstall_addon:
        yield uninstall_addon


def mock_addon_options(addon_info: AsyncMock) -> dict[str, Any]:
    """Mock add-on options."""
    return addon_info.return_value["options"]


def mock_set_addon_options_side_effect(addon_options: dict[str, Any]) -> Any | None:
    """Return the set add-on options side effect."""

    async def set_addon_options(hass: HomeAssistant, slug: str, options: dict) -> None:
        """Mock set add-on options."""
        addon_options.update(options["options"])

    return set_addon_options


def mock_set_addon_options(
    set_addon_options_side_effect: Any | None,
) -> Generator[AsyncMock]:
    """Mock set add-on options."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_set_addon_options",
        side_effect=set_addon_options_side_effect,
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
