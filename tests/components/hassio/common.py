"""Provide common test tools for hassio."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import fields
import logging
from types import MethodType
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohasupervisor.models import (
    AddonsOptions,
    AddonsStats,
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
ADDONS_STATS_FIELDS = [field.name for field in fields(AddonsStats)]

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


def mock_set_addon_options_side_effect(addon_options: dict[str, Any]) -> Any | None:
    """Return the set add-on options side effect."""

    async def set_addon_options(slug: str, options: AddonsOptions) -> None:
        """Mock set add-on options."""
        addon_options.update(options.config)

    return set_addon_options


def mock_create_backup() -> Generator[AsyncMock]:
    """Mock create backup."""
    with patch(
        "homeassistant.components.hassio.addon_manager.async_create_backup"
    ) as create_backup:
        yield create_backup


def mock_addon_stats(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock addon stats."""
    supervisor_client.addons.addon_stats.return_value = addon_stats = Mock(
        spec=AddonsStats,
        cpu_percent=0.99,
        memory_usage=182611968,
        memory_limit=3977146368,
        memory_percent=4.59,
        network_rx=362570232,
        network_tx=82374138,
        blk_read=46010945536,
        blk_write=15051526144,
    )
    addon_stats.to_dict = MethodType(
        lambda self: mock_to_dict(self, ADDONS_STATS_FIELDS),
        addon_stats,
    )
    return supervisor_client.addons.addon_stats
