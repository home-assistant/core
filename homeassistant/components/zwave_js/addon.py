"""Provide add-on management."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from functools import partial
from typing import Any, TypeVar

from typing_extensions import ParamSpec

from homeassistant.components.hassio import (
    async_create_backup,
    async_get_addon_discovery_info,
    async_get_addon_info,
    async_get_addon_store_info,
    async_install_addon,
    async_restart_addon,
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

from .const import (
    ADDON_SLUG,
    CONF_ADDON_DEVICE,
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
    DOMAIN,
    LOGGER,
)

_R = TypeVar("_R")
_P = ParamSpec("_P")

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass)


def api_error(
    error_message: str,
) -> Callable[[Callable[_P, Awaitable[_R]]], Callable[_P, Coroutine[Any, Any, _R]]]:
    """Handle HassioAPIError and raise a specific AddonError."""

    def handle_hassio_api_error(
        func: Callable[_P, Awaitable[_R]]
    ) -> Callable[_P, Coroutine[Any, Any, _R]]:
        """Handle a HassioAPIError."""

        async def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """Wrap an add-on manager method."""
            try:
                return_value = await func(*args, **kwargs)
            except HassioAPIError as err:
                raise AddonError(f"{error_message}: {err}") from err

            return return_value

        return wrapper

    return handle_hassio_api_error


@dataclass
class AddonInfo:
    """Represent the current add-on info state."""

    options: dict[str, Any]
    state: AddonState
    update_available: bool
    version: str | None


class AddonState(Enum):
    """Represent the current state of the add-on."""

    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    UPDATING = "updating"
    NOT_RUNNING = "not_running"
    RUNNING = "running"


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
        self._restart_task: asyncio.Task | None = None
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
    async def async_get_addon_info(self) -> AddonInfo:
        """Return and cache Z-Wave JS add-on info."""
        addon_store_info = await async_get_addon_store_info(self._hass, ADDON_SLUG)
        LOGGER.debug("Add-on store info: %s", addon_store_info)
        if not addon_store_info["installed"]:
            return AddonInfo(
                options={},
                state=AddonState.NOT_INSTALLED,
                update_available=False,
                version=None,
            )

        addon_info = await async_get_addon_info(self._hass, ADDON_SLUG)
        addon_state = self.async_get_addon_state(addon_info)
        return AddonInfo(
            options=addon_info["options"],
            state=addon_state,
            update_available=addon_info["update_available"],
            version=addon_info["version"],
        )

    @callback
    def async_get_addon_state(self, addon_info: dict[str, Any]) -> AddonState:
        """Return the current state of the Z-Wave JS add-on."""
        addon_state = AddonState.NOT_RUNNING

        if addon_info["state"] == "started":
            addon_state = AddonState.RUNNING
        if self._install_task and not self._install_task.done():
            addon_state = AddonState.INSTALLING
        if self._update_task and not self._update_task.done():
            addon_state = AddonState.UPDATING

        return addon_state

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
        self,
        usb_path: str,
        s0_legacy_key: str,
        s2_access_control_key: str,
        s2_authenticated_key: str,
        s2_unauthenticated_key: str,
        catch_error: bool = False,
    ) -> asyncio.Task:
        """Schedule a task that installs and sets up the Z-Wave JS add-on.

        Only schedule a new install task if the there's no running task.
        """
        if not self._install_task or self._install_task.done():
            LOGGER.info("Z-Wave JS add-on is not installed. Installing add-on")
            self._install_task = self._async_schedule_addon_operation(
                self.async_install_addon,
                partial(
                    self.async_configure_addon,
                    usb_path,
                    s0_legacy_key,
                    s2_access_control_key,
                    s2_authenticated_key,
                    s2_unauthenticated_key,
                ),
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

        if addon_info.state is AddonState.NOT_INSTALLED:
            raise AddonError("Z-Wave JS add-on is not installed")

        if not addon_info.update_available:
            return

        await self.async_create_backup()
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

    @api_error("Failed to restart the Z-Wave JS add-on")
    async def async_restart_addon(self) -> None:
        """Restart the Z-Wave JS add-on."""
        await async_restart_addon(self._hass, ADDON_SLUG)

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

    @callback
    def async_schedule_restart_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that restarts the Z-Wave JS add-on.

        Only schedule a new restart task if the there's no running task.
        """
        if not self._restart_task or self._restart_task.done():
            LOGGER.info("Restarting Z-Wave JS add-on")
            self._restart_task = self._async_schedule_addon_operation(
                self.async_restart_addon, catch_error=catch_error
            )
        return self._restart_task

    @api_error("Failed to stop the Z-Wave JS add-on")
    async def async_stop_addon(self) -> None:
        """Stop the Z-Wave JS add-on."""
        await async_stop_addon(self._hass, ADDON_SLUG)

    async def async_configure_addon(
        self,
        usb_path: str,
        s0_legacy_key: str,
        s2_access_control_key: str,
        s2_authenticated_key: str,
        s2_unauthenticated_key: str,
    ) -> None:
        """Configure and start Z-Wave JS add-on."""
        addon_info = await self.async_get_addon_info()

        if addon_info.state is AddonState.NOT_INSTALLED:
            raise AddonError("Z-Wave JS add-on is not installed")

        new_addon_options = {
            CONF_ADDON_DEVICE: usb_path,
            CONF_ADDON_S0_LEGACY_KEY: s0_legacy_key,
            CONF_ADDON_S2_ACCESS_CONTROL_KEY: s2_access_control_key,
            CONF_ADDON_S2_AUTHENTICATED_KEY: s2_authenticated_key,
            CONF_ADDON_S2_UNAUTHENTICATED_KEY: s2_unauthenticated_key,
        }

        if new_addon_options != addon_info.options:
            await self.async_set_addon_options(new_addon_options)

    @callback
    def async_schedule_setup_addon(
        self,
        usb_path: str,
        s0_legacy_key: str,
        s2_access_control_key: str,
        s2_authenticated_key: str,
        s2_unauthenticated_key: str,
        catch_error: bool = False,
    ) -> asyncio.Task:
        """Schedule a task that configures and starts the Z-Wave JS add-on.

        Only schedule a new setup task if the there's no running task.
        """
        if not self._start_task or self._start_task.done():
            LOGGER.info("Z-Wave JS add-on is not running. Starting add-on")
            self._start_task = self._async_schedule_addon_operation(
                partial(
                    self.async_configure_addon,
                    usb_path,
                    s0_legacy_key,
                    s2_access_control_key,
                    s2_authenticated_key,
                    s2_unauthenticated_key,
                ),
                self.async_start_addon,
                catch_error=catch_error,
            )
        return self._start_task

    @api_error("Failed to create a backup of the Z-Wave JS add-on.")
    async def async_create_backup(self) -> None:
        """Create a partial backup of the Z-Wave JS add-on."""
        addon_info = await self.async_get_addon_info()
        name = f"addon_{ADDON_SLUG}_{addon_info.version}"

        LOGGER.debug("Creating backup: %s", name)
        await async_create_backup(
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
