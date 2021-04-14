"""Provide add-on management."""
from __future__ import annotations

import asyncio
from functools import partial
from typing import Any, Callable, TypeVar, cast

from homeassistant.components.hassio import (
    async_create_snapshot,
    async_get_addon_discovery_info,
    async_get_addon_info,
    async_install_addon,
    async_set_addon_options,
    async_start_addon,
    async_stop_addon,
    async_uninstall_addon,
    async_update_addon,
)
from homeassistant.components.hassio.handler import HassioAPIError
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.singleton import singleton

from .const import ADDON_SLUG, CONF_ADDON_DEVICE, CONF_ADDON_NETWORK_KEY, DOMAIN, LOGGER

F = TypeVar("F", bound=Callable[..., Any])  # pylint: disable=invalid-name

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass)


def api_error(error_message: str) -> Callable[[F], F]:
    """Handle HassioAPIError and raise a specific AddonError."""

    def handle_hassio_api_error(func: F) -> F:
        """Handle a HassioAPIError."""

        async def wrapper(*args, **kwargs):  # type: ignore
            """Wrap an add-on manager method."""
            try:
                return_value = await func(*args, **kwargs)
            except HassioAPIError as err:
                raise AddonError(error_message) from err

            return return_value

        return cast(F, wrapper)

    return handle_hassio_api_error


class AddonManager:
    """Manage the add-on.

    Methods may raise AddonError.
    Only one instance of this class may exist
    to keep track of running add-on tasks.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the add-on manager."""
        self._hass = hass
        self._install_task: asyncio.Task | None = None
        self._start_task: asyncio.Task | None = None
        self._update_task: asyncio.Task | None = None

    def task_in_progress(self) -> bool:
        """Return True if any of the add-on tasks are in progress."""
        return any(
            task and not task.done()
            for task in (
                self._install_task,
                self._start_task,
                self._update_task,
            )
        )

    @api_error("Failed to get Z-Wave JS add-on discovery info")
    async def async_get_addon_discovery_info(self) -> dict:
        """Return add-on discovery info."""
        discovery_info = await async_get_addon_discovery_info(self._hass, ADDON_SLUG)

        if not discovery_info:
            raise AddonError("Failed to get Z-Wave JS add-on discovery info")

        discovery_info_config: dict = discovery_info["config"]
        return discovery_info_config

    @api_error("Failed to get the Z-Wave JS add-on info")
    async def async_get_addon_info(self) -> dict:
        """Return and cache Z-Wave JS add-on info."""
        addon_info: dict = await async_get_addon_info(self._hass, ADDON_SLUG)
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

    @api_error("Failed to set the Z-Wave JS add-on options")
    async def async_set_addon_options(self, config: dict) -> None:
        """Set Z-Wave JS add-on options."""
        options = {"options": config}
        await async_set_addon_options(self._hass, ADDON_SLUG, options)

    @api_error("Failed to install the Z-Wave JS add-on")
    async def async_install_addon(self) -> None:
        """Install the Z-Wave JS add-on."""
        await async_install_addon(self._hass, ADDON_SLUG)

    @callback
    def async_schedule_install_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that installs the Z-Wave JS add-on.

        Only schedule a new install task if the there's no running task.
        """
        if not self._install_task or self._install_task.done():
            LOGGER.info("Z-Wave JS add-on is not installed. Installing add-on")
            self._install_task = self._async_schedule_addon_operation(
                self.async_install_addon, catch_error=catch_error
            )
        return self._install_task

    @callback
    def async_schedule_install_setup_addon(
        self, usb_path: str, network_key: str, catch_error: bool = False
    ) -> asyncio.Task:
        """Schedule a task that installs and sets up the Z-Wave JS add-on.

        Only schedule a new install task if the there's no running task.
        """
        if not self._install_task or self._install_task.done():
            LOGGER.info("Z-Wave JS add-on is not installed. Installing add-on")
            self._install_task = self._async_schedule_addon_operation(
                self.async_install_addon,
                partial(self.async_configure_addon, usb_path, network_key),
                self.async_start_addon,
                catch_error=catch_error,
            )
        return self._install_task

    @api_error("Failed to uninstall the Z-Wave JS add-on")
    async def async_uninstall_addon(self) -> None:
        """Uninstall the Z-Wave JS add-on."""
        await async_uninstall_addon(self._hass, ADDON_SLUG)

    @api_error("Failed to update the Z-Wave JS add-on")
    async def async_update_addon(self) -> None:
        """Update the Z-Wave JS add-on if needed."""
        addon_info = await self.async_get_addon_info()
        addon_version = addon_info["version"]
        update_available = addon_info["update_available"]

        if addon_version is None:
            raise AddonError("Z-Wave JS add-on is not installed")

        if not update_available:
            return

        await self.async_create_snapshot()
        await async_update_addon(self._hass, ADDON_SLUG)

    @callback
    def async_schedule_update_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that updates and sets up the Z-Wave JS add-on.

        Only schedule a new update task if the there's no running task.
        """
        if not self._update_task or self._update_task.done():
            LOGGER.info("Trying to update the Z-Wave JS add-on")
            self._update_task = self._async_schedule_addon_operation(
                self.async_update_addon,
                catch_error=catch_error,
            )
        return self._update_task

    @api_error("Failed to start the Z-Wave JS add-on")
    async def async_start_addon(self) -> None:
        """Start the Z-Wave JS add-on."""
        await async_start_addon(self._hass, ADDON_SLUG)

    @callback
    def async_schedule_start_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that starts the Z-Wave JS add-on.

        Only schedule a new start task if the there's no running task.
        """
        if not self._start_task or self._start_task.done():
            LOGGER.info("Z-Wave JS add-on is not running. Starting add-on")
            self._start_task = self._async_schedule_addon_operation(
                self.async_start_addon, catch_error=catch_error
            )
        return self._start_task

    @api_error("Failed to stop the Z-Wave JS add-on")
    async def async_stop_addon(self) -> None:
        """Stop the Z-Wave JS add-on."""
        await async_stop_addon(self._hass, ADDON_SLUG)

    async def async_configure_addon(self, usb_path: str, network_key: str) -> None:
        """Configure and start Z-Wave JS add-on."""
        addon_options = await self.async_get_addon_options()

        new_addon_options = {
            CONF_ADDON_DEVICE: usb_path,
            CONF_ADDON_NETWORK_KEY: network_key,
        }

        if new_addon_options != addon_options:
            await self.async_set_addon_options(new_addon_options)

    @callback
    def async_schedule_setup_addon(
        self, usb_path: str, network_key: str, catch_error: bool = False
    ) -> asyncio.Task:
        """Schedule a task that configures and starts the Z-Wave JS add-on.

        Only schedule a new setup task if the there's no running task.
        """
        if not self._start_task or self._start_task.done():
            LOGGER.info("Z-Wave JS add-on is not running. Starting add-on")
            self._start_task = self._async_schedule_addon_operation(
                partial(self.async_configure_addon, usb_path, network_key),
                self.async_start_addon,
                catch_error=catch_error,
            )
        return self._start_task

    @api_error("Failed to create a snapshot of the Z-Wave JS add-on.")
    async def async_create_snapshot(self) -> None:
        """Create a partial snapshot of the Z-Wave JS add-on."""
        addon_info = await self.async_get_addon_info()
        addon_version = addon_info["version"]
        name = f"addon_{ADDON_SLUG}_{addon_version}"

        LOGGER.debug("Creating snapshot: %s", name)
        await async_create_snapshot(
            self._hass,
            {"name": name, "addons": [ADDON_SLUG]},
            partial=True,
        )

    @callback
    def _async_schedule_addon_operation(
        self, *funcs: Callable, catch_error: bool = False
    ) -> asyncio.Task:
        """Schedule an add-on task."""

        async def addon_operation() -> None:
            """Do the add-on operation and catch AddonError."""
            for func in funcs:
                try:
                    await func()
                except AddonError as err:
                    if not catch_error:
                        raise
                    LOGGER.error(err)
                    break

        return self._hass.async_create_task(addon_operation())


class AddonError(HomeAssistantError):
    """Represent an error with Z-Wave JS add-on."""
