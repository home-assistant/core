"""Provide add-on management."""
from __future__ import annotations

import asyncio
from functools import partial
from typing import Callable, Optional, cast

from homeassistant.components.hassio import (
    async_get_addon_info,
    async_install_addon,
    async_set_addon_options,
    async_start_addon,
    async_stop_addon,
    async_uninstall_addon,
    async_update_addon,
)
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.singleton import singleton

from .const import (
    ADDON_SLUG,
    CONF_ADDON_DEVICE,
    CONF_ADDON_NETWORK_KEY,
    CONF_NETWORK_KEY,
    CONF_USB_PATH,
    DOMAIN,
    LOGGER,
)

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass)


async def async_ensure_addon_running(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ensure that Z-Wave JS add-on is installed and running."""
    addon_manager: AddonManager = get_addon_manager(hass)
    try:
        addon_is_installed = await addon_manager.async_is_addon_installed()
        addon_is_running = await addon_manager.async_is_addon_running()
    except AddonError as err:
        LOGGER.error("Failed to get the Z-Wave JS add-on info")
        raise ConfigEntryNotReady from err

    usb_path: str = entry.data[CONF_USB_PATH]
    network_key: str = entry.data[CONF_NETWORK_KEY]

    if not addon_is_installed:
        LOGGER.warning("Z-Wave JS add-on is not installed. Installing add-on")
        addon_manager.async_schedule_install_addon(usb_path, network_key)
        raise ConfigEntryNotReady

    if not addon_is_running:
        LOGGER.warning("Z-Wave JS add-on is not running. Starting add-on")
        addon_manager.async_schedule_setup_addon(usb_path, network_key)
        raise ConfigEntryNotReady


@callback
def async_ensure_addon_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Ensure that Z-Wave JS add-on is updated and running."""
    addon_manager: AddonManager = get_addon_manager(hass)
    usb_path: str = entry.data[CONF_USB_PATH]
    network_key: str = entry.data[CONF_NETWORK_KEY]
    LOGGER.warning("Trying to update the Z-Wave JS add-on")
    addon_manager.async_schedule_update_addon(usb_path, network_key)


class AddonManager:
    """Manage the add-on.

    Methods may raise AddonError.
    Only one instance of this class may exist
    to keep track of running add-on tasks.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the add-on manager."""
        self._hass = hass
        self._install_task: Optional[asyncio.Task] = None
        self._update_task: Optional[asyncio.Task] = None
        self._setup_task: Optional[asyncio.Task] = None

    async def async_get_addon_info(self) -> dict:
        """Return and cache Z-Wave JS add-on info."""
        try:
            addon_info: dict = await async_get_addon_info(self._hass, ADDON_SLUG)
        except HassioAPIError as err:
            raise AddonError("Failed to get the Z-Wave JS add-on info") from err

        return addon_info

    async def async_is_addon_running(self) -> bool:
        """Return True if Z-Wave JS add-on is running."""
        addon_info = await self.async_get_addon_info()
        return bool(addon_info["state"] == "started")

    async def async_is_addon_installed(self) -> bool:
        """Return True if Z-Wave JS add-on is installed."""
        addon_info = await self.async_get_addon_info()
        return addon_info["version"] is not None

    async def async_get_addon_options(self) -> dict:
        """Get Z-Wave JS add-on options."""
        addon_info = await self.async_get_addon_info()
        return cast(dict, addon_info["options"])

    async def async_set_addon_options(self, config: dict) -> None:
        """Set Z-Wave JS add-on options."""
        options = {"options": config}
        try:
            await async_set_addon_options(self._hass, ADDON_SLUG, options)
        except HassioAPIError as err:
            raise AddonError("Failed to set the Z-Wave JS add-on options") from err

    async def async_install_addon(self) -> None:
        """Install the Z-Wave JS add-on."""
        try:
            await async_install_addon(self._hass, ADDON_SLUG)
        except HassioAPIError as err:
            raise AddonError("Failed to install the Z-Wave JS add-on") from err

    @callback
    def async_schedule_install_addon(
        self, usb_path: str, network_key: str
    ) -> asyncio.Task:
        """Schedule a task that installs and sets up the Z-Wave JS add-on.

        Only schedule a new install task if the there's no running task.
        """
        if not self._install_task or self._install_task.done():
            self._install_task = self._async_schedule_addon_operation(
                self.async_install_addon,
                partial(self.async_setup_addon, usb_path, network_key),
            )
        return self._install_task

    async def async_uninstall_addon(self) -> None:
        """Uninstall the Z-Wave JS add-on."""
        try:
            await async_uninstall_addon(ADDON_SLUG)
        except HassioAPIError as err:
            raise AddonError("Failed to uninstall the Z-Wave JS add-on") from err

    async def async_update_addon(self) -> None:
        """Update the Z-Wave JS add-on if needed."""
        addon_info = await self.async_get_addon_info()
        addon_version = addon_info["version"]
        addon_latest_version = addon_info["version_latest"]

        if addon_version is None:
            raise AddonError("Z-Wave JS add-on is not installed")

        if addon_version >= addon_latest_version:
            return

        try:
            await async_update_addon(self._hass, ADDON_SLUG)
        except HassioAPIError as err:
            raise AddonError("Failed to update the Z-Wave JS add-on") from err

    @callback
    def async_schedule_update_addon(
        self, usb_path: str, network_key: str
    ) -> asyncio.Task:
        """Schedule a task that updates and sets up the Z-Wave JS add-on.

        Only schedule a new update task if the there's no running task.
        """
        if not self._update_task or self._update_task.done():
            self._update_task = self._async_schedule_addon_operation(
                self.async_update_addon,
                partial(self.async_setup_addon, usb_path, network_key),
            )
        return self._update_task

    async def async_start_addon(self) -> None:
        """Start the Z-Wave JS add-on."""
        try:
            await async_start_addon(self._hass, ADDON_SLUG)
        except HassioAPIError as err:
            raise AddonError("Failed to start the Z-Wave JS add-on") from err

    async def async_stop_addon(self) -> None:
        """Stop the Z-Wave JS add-on."""
        try:
            await async_stop_addon(self._hass, ADDON_SLUG)
        except HassioAPIError as err:
            raise AddonError("Failed to stop the Z-Wave JS add-on") from err

    async def async_setup_addon(self, usb_path: str, network_key: str) -> None:
        """Configure and start Z-Wave JS add-on."""
        addon_options = await self.async_get_addon_options()

        new_addon_options = {
            CONF_ADDON_DEVICE: usb_path,
            CONF_ADDON_NETWORK_KEY: network_key,
        }

        if new_addon_options != addon_options:
            await self.async_set_addon_options(new_addon_options)

        await self.async_start_addon()

    @callback
    def async_schedule_setup_addon(
        self, usb_path: str, network_key: str
    ) -> asyncio.Task:
        """Schedule a task that configures and starts the Z-Wave JS add-on.

        Only schedule a new setup task if the there's no running task.
        """
        if not self._setup_task or self._setup_task.done():
            self._setup_task = self._async_schedule_addon_operation(
                partial(self.async_setup_addon, usb_path, network_key)
            )
        return self._setup_task

    @callback
    def _async_schedule_addon_operation(self, *funcs: Callable) -> asyncio.Task:
        """Schedule an add-on task."""

        async def addon_operation() -> None:
            """Do the add-on operation and catch AddonError."""
            for func in funcs:
                try:
                    await func()
                except AddonError as err:
                    LOGGER.error(err)

        return self._hass.async_create_task(addon_operation())


class AddonError(HomeAssistantError):
    """Represent an error with Z-Wave JS add-on."""
