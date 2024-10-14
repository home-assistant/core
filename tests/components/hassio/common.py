"""Provide common test tools for hassio."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import fields
import logging
from types import MethodType
from typing import Any
from unittest.mock import DEFAULT, AsyncMock, Mock, patch

from aiohasupervisor.models import (
    AddonStage,
    InstalledAddonComplete,
    Repository,
    StoreAddon,
    StoreAddonComplete,
)

from homeassistant.components.hassio.addon_manager import AddonManager
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)
INSTALLED_ADDON_FIELDS = [field.name for field in fields(InstalledAddonComplete)]
STORE_ADDON_FIELDS = [field.name for field in fields(StoreAddonComplete)]

MOCK_STORE_ADDONS = [
    StoreAddon(
        name="test",
        arch=[],
        documentation=False,
        advanced=False,
        available=True,
        build=False,
        description="Test add-on service",
        homeassistant=None,
        icon=False,
        logo=False,
        repository="core",
        slug="core_test",
        stage=AddonStage.EXPERIMENTAL,
        update_available=False,
        url="https://example.com/addons/tree/master/test",
        version_latest="1.0.0",
        version="1.0.0",
        installed=True,
    )
]

MOCK_REPOSITORIES = [
    Repository(
        slug="core",
        name="Official add-ons",
        source="core",
        url="https://home-assistant.io/addons",
        maintainer="Home Assistant",
    )
]


def mock_to_dict(obj: Mock, fields: list[str]) -> dict[str, Any]:
    """Aiohasupervisor mocks to dictionary representation."""
    return {
        field: getattr(obj, field)
        for field in fields
        if not isinstance(getattr(obj, field), Mock)
    }


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
    supervisor_client: AsyncMock,
    addon_store_info_side_effect: Any | None,
) -> AsyncMock:
    """Mock Supervisor add-on store info."""
    supervisor_client.store.addon_info.side_effect = addon_store_info_side_effect

    supervisor_client.store.addon_info.return_value = addon_info = Mock(
        spec=StoreAddonComplete,
        slug="test",
        repository="core",
        available=True,
        installed=False,
        update_available=False,
        version="1.0.0",
        supervisor_api=False,
        supervisor_role="default",
    )
    addon_info.name = "test"
    addon_info.to_dict = MethodType(
        lambda self: mock_to_dict(self, STORE_ADDON_FIELDS),
        addon_info,
    )
    return supervisor_client.store.addon_info


def mock_addon_info(
    supervisor_client: AsyncMock, addon_info_side_effect: Any | None
) -> AsyncMock:
    """Mock Supervisor add-on info."""
    supervisor_client.addons.addon_info.side_effect = addon_info_side_effect

    supervisor_client.addons.addon_info.return_value = addon_info = Mock(
        spec=InstalledAddonComplete,
        slug="test",
        repository="core",
        available=False,
        hostname="",
        options={},
        state="unknown",
        update_available=False,
        version=None,
        supervisor_api=False,
        supervisor_role="default",
    )
    addon_info.name = "test"
    addon_info.to_dict = MethodType(
        lambda self: mock_to_dict(self, INSTALLED_ADDON_FIELDS),
        addon_info,
    )
    return supervisor_client.addons.addon_info


def mock_addon_not_installed(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on not installed."""
    addon_store_info.return_value.available = True
    return addon_info


def mock_addon_installed(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already installed but not running."""
    addon_store_info.return_value.available = True
    addon_store_info.return_value.installed = True
    addon_info.return_value.available = True
    addon_info.return_value.hostname = "core-test-addon"
    addon_info.return_value.state = "stopped"
    addon_info.return_value.version = "1.0.0"
    return addon_info


def mock_addon_running(addon_store_info: AsyncMock, addon_info: AsyncMock) -> AsyncMock:
    """Mock add-on already running."""
    addon_store_info.return_value.available = True
    addon_store_info.return_value.installed = True
    addon_info.return_value.state = "started"
    return addon_info


def mock_install_addon_side_effect(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the install add-on side effect."""

    async def install_addon(addon: str):
        """Mock install add-on."""
        addon_store_info.return_value.available = True
        addon_store_info.return_value.installed = True
        addon_info.return_value.available = True
        addon_info.return_value.state = "stopped"
        addon_info.return_value.version = "1.0.0"

    return install_addon


def mock_start_addon_side_effect(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the start add-on options side effect."""

    async def start_addon(addon: str) -> None:
        """Mock start add-on."""
        addon_store_info.return_value.available = True
        addon_store_info.return_value.installed = True
        addon_info.return_value.available = True
        addon_info.return_value.state = "started"

    return start_addon


def mock_addon_options(addon_info: AsyncMock) -> dict[str, Any]:
    """Mock add-on options."""
    return addon_info.return_value.options


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
