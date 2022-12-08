"""Provide add-on management."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from enum import Enum
from functools import partial, wraps
import logging
from typing import Any, TypeVar

from typing_extensions import Concatenate, ParamSpec

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .handler import (
    HassioAPIError,
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

_AddonManagerT = TypeVar("_AddonManagerT", bound="AddonManager")
_R = TypeVar("_R")
_P = ParamSpec("_P")


def api_error(
    error_message: str,
) -> Callable[
    [Callable[Concatenate[_AddonManagerT, _P], Awaitable[_R]]],
    Callable[Concatenate[_AddonManagerT, _P], Coroutine[Any, Any, _R]],
]:
    """Handle HassioAPIError and raise a specific AddonError."""

    def handle_hassio_api_error(
        func: Callable[Concatenate[_AddonManagerT, _P], Awaitable[_R]]
    ) -> Callable[Concatenate[_AddonManagerT, _P], Coroutine[Any, Any, _R]]:
        """Handle a HassioAPIError."""

        @wraps(func)
        async def wrapper(
            self: _AddonManagerT, *args: _P.args, **kwargs: _P.kwargs
        ) -> _R:
            """Wrap an add-on manager method."""
            try:
                return_value = await func(self, *args, **kwargs)
            except HassioAPIError as err:
                raise AddonError(
                    f"{error_message.format(addon_name=self.addon_name)}: {err}"
                ) from err

            return return_value

        return wrapper

    return handle_hassio_api_error


@dataclass
class AddonInfo:
    """Represent the current add-on info state."""

    hostname: str | None
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
    Only one instance of this class may exist per add-on
    to keep track of running add-on tasks.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        addon_name: str,
        addon_slug: str,
    ) -> None:
        """Set up the add-on manager."""
        self.addon_name = addon_name
        self.addon_slug = addon_slug
        self._hass = hass
        self._logger = logger
        self._install_task: asyncio.Task | None = None
        self._restart_task: asyncio.Task | None = None
        self._start_task: asyncio.Task | None = None
        self._update_task: asyncio.Task | None = None

    def task_in_progress(self) -> bool:
        """Return True if any of the add-on tasks are in progress."""
        return any(
            task and not task.done()
            for task in (
                self._restart_task,
                self._install_task,
                self._start_task,
                self._update_task,
            )
        )

    @api_error("Failed to get the {addon_name} add-on discovery info")
    async def async_get_addon_discovery_info(self) -> dict:
        """Return add-on discovery info."""
        discovery_info = await async_get_addon_discovery_info(
            self._hass, self.addon_slug
        )

        if not discovery_info:
            raise AddonError(f"Failed to get {self.addon_name} add-on discovery info")

        discovery_info_config: dict = discovery_info["config"]
        return discovery_info_config

    @api_error("Failed to get the {addon_name} add-on info")
    async def async_get_addon_info(self) -> AddonInfo:
        """Return and cache manager add-on info."""
        addon_store_info = await async_get_addon_store_info(self._hass, self.addon_slug)
        self._logger.debug("Add-on store info: %s", addon_store_info)
        if not addon_store_info["installed"]:
            return AddonInfo(
                hostname=None,
                options={},
                state=AddonState.NOT_INSTALLED,
                update_available=False,
                version=None,
            )

        addon_info = await async_get_addon_info(self._hass, self.addon_slug)
        addon_state = self.async_get_addon_state(addon_info)
        return AddonInfo(
            hostname=addon_info["hostname"],
            options=addon_info["options"],
            state=addon_state,
            update_available=addon_info["update_available"],
            version=addon_info["version"],
        )

    @callback
    def async_get_addon_state(self, addon_info: dict[str, Any]) -> AddonState:
        """Return the current state of the managed add-on."""
        addon_state = AddonState.NOT_RUNNING

        if addon_info["state"] == "started":
            addon_state = AddonState.RUNNING
        if self._install_task and not self._install_task.done():
            addon_state = AddonState.INSTALLING
        if self._update_task and not self._update_task.done():
            addon_state = AddonState.UPDATING

        return addon_state

    @api_error("Failed to set the {addon_name} add-on options")
    async def async_set_addon_options(self, config: dict) -> None:
        """Set manager add-on options."""
        options = {"options": config}
        await async_set_addon_options(self._hass, self.addon_slug, options)

    @api_error("Failed to install the {addon_name} add-on")
    async def async_install_addon(self) -> None:
        """Install the managed add-on."""
        await async_install_addon(self._hass, self.addon_slug)

    @api_error("Failed to uninstall the {addon_name} add-on")
    async def async_uninstall_addon(self) -> None:
        """Uninstall the managed add-on."""
        await async_uninstall_addon(self._hass, self.addon_slug)

    @api_error("Failed to update the {addon_name} add-on")
    async def async_update_addon(self) -> None:
        """Update the managed add-on if needed."""
        addon_info = await self.async_get_addon_info()

        if addon_info.state is AddonState.NOT_INSTALLED:
            raise AddonError(f"{self.addon_name} add-on is not installed")

        if not addon_info.update_available:
            return

        await self.async_create_backup()
        await async_update_addon(self._hass, self.addon_slug)

    @api_error("Failed to start the {addon_name} add-on")
    async def async_start_addon(self) -> None:
        """Start the managed add-on."""
        await async_start_addon(self._hass, self.addon_slug)

    @api_error("Failed to restart the {addon_name} add-on")
    async def async_restart_addon(self) -> None:
        """Restart the managed add-on."""
        await async_restart_addon(self._hass, self.addon_slug)

    @api_error("Failed to stop the {addon_name} add-on")
    async def async_stop_addon(self) -> None:
        """Stop the managed add-on."""
        await async_stop_addon(self._hass, self.addon_slug)

    @api_error("Failed to create a backup of the {addon_name} add-on")
    async def async_create_backup(self) -> None:
        """Create a partial backup of the managed add-on."""
        addon_info = await self.async_get_addon_info()
        name = f"addon_{self.addon_slug}_{addon_info.version}"

        self._logger.debug("Creating backup: %s", name)
        await async_create_backup(
            self._hass,
            {"name": name, "addons": [self.addon_slug]},
            partial=True,
        )

    async def async_configure_addon(
        self,
        addon_config: dict[str, Any],
    ) -> None:
        """Configure the manager add-on, if needed."""
        addon_info = await self.async_get_addon_info()

        if addon_info.state is AddonState.NOT_INSTALLED:
            raise AddonError(f"{self.addon_name} add-on is not installed")

        if addon_config != addon_info.options:
            await self.async_set_addon_options(addon_config)

    @callback
    def async_schedule_install_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that installs the managed add-on.

        Only schedule a new install task if the there's no running task.
        """
        if not self._install_task or self._install_task.done():
            self._logger.info(
                "%s add-on is not installed. Installing add-on", self.addon_name
            )
            self._install_task = self._async_schedule_addon_operation(
                self.async_install_addon, catch_error=catch_error
            )
        return self._install_task

    @callback
    def async_schedule_install_setup_addon(
        self,
        addon_config: dict[str, Any],
        catch_error: bool = False,
    ) -> asyncio.Task:
        """Schedule a task that installs and sets up the managed add-on.

        Only schedule a new install task if the there's no running task.
        """
        if not self._install_task or self._install_task.done():
            self._logger.info(
                "%s add-on is not installed. Installing add-on", self.addon_name
            )
            self._install_task = self._async_schedule_addon_operation(
                self.async_install_addon,
                partial(
                    self.async_configure_addon,
                    addon_config,
                ),
                self.async_start_addon,
                catch_error=catch_error,
            )
        return self._install_task

    @callback
    def async_schedule_update_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that updates and sets up the managed add-on.

        Only schedule a new update task if the there's no running task.
        """
        if not self._update_task or self._update_task.done():
            self._logger.info("Trying to update the %s add-on", self.addon_name)
            self._update_task = self._async_schedule_addon_operation(
                self.async_update_addon,
                catch_error=catch_error,
            )
        return self._update_task

    @callback
    def async_schedule_start_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that starts the managed add-on.

        Only schedule a new start task if the there's no running task.
        """
        if not self._start_task or self._start_task.done():
            self._logger.info(
                "%s add-on is not running. Starting add-on", self.addon_name
            )
            self._start_task = self._async_schedule_addon_operation(
                self.async_start_addon, catch_error=catch_error
            )
        return self._start_task

    @callback
    def async_schedule_restart_addon(self, catch_error: bool = False) -> asyncio.Task:
        """Schedule a task that restarts the managed add-on.

        Only schedule a new restart task if the there's no running task.
        """
        if not self._restart_task or self._restart_task.done():
            self._logger.info("Restarting %s add-on", self.addon_name)
            self._restart_task = self._async_schedule_addon_operation(
                self.async_restart_addon, catch_error=catch_error
            )
        return self._restart_task

    @callback
    def async_schedule_setup_addon(
        self,
        addon_config: dict[str, Any],
        catch_error: bool = False,
    ) -> asyncio.Task:
        """Schedule a task that configures and starts the managed add-on.

        Only schedule a new setup task if there's no running task.
        """
        if not self._start_task or self._start_task.done():
            self._logger.info(
                "%s add-on is not running. Starting add-on", self.addon_name
            )
            self._start_task = self._async_schedule_addon_operation(
                partial(
                    self.async_configure_addon,
                    addon_config,
                ),
                self.async_start_addon,
                catch_error=catch_error,
            )
        return self._start_task

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
                    self._logger.error(err)
                    break

        return self._hass.async_create_task(addon_operation())


class AddonError(HomeAssistantError):
    """Represent an error with the managed add-on."""
