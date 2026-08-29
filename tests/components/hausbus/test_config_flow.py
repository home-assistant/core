"""Config flow for Haus-Bus integration."""

import asyncio
import contextlib
import logging
from typing import Any, override

from pyhausbus.HomeServer import HomeServer
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN
from .gateway import async_acquire_home_server, async_release_home_server

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({})

_DEVICE_SEARCH_TIMEOUT = 5  # seconds


class HausBusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for hausbus."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._search_task: asyncio.Task[None] | None = None
        self.home_server: HomeServer | None = None

    @override
    def async_remove(self) -> None:
        """Release this flow's HomeServer reference, if it acquired one."""

        async def _cleanup() -> None:
            search_task = self._search_task
            self._search_task = None

            if search_task is not None:
                search_task.cancel()

                with contextlib.suppress(asyncio.CancelledError):
                    await search_task

            if self.home_server is not None:
                await async_release_home_server(
                    self.hass,
                    self.home_server,
                )
                self.home_server = None

        self.hass.async_create_task(_cleanup())

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        if user_input is not None:
            return await self.async_step_wait_for_device()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors={},
        )

    async def async_step_wait_for_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Wait for a Haus-Bus device to be found."""

        if self._search_task is None:
            self._search_task = self.hass.async_create_task(
                self._async_wait_for_device()
            )

        if not self._search_task.done():
            return self.async_show_progress(
                step_id="wait_for_device",
                progress_action="wait_for_device",
                progress_task=self._search_task,
            )

        try:
            await self._search_task

        except (TimeoutError, OSError):
            return self.async_show_progress_done(
                next_step_id="search_timeout"
            )

        finally:
            self._search_task = None

        return self.async_show_progress_done(
            next_step_id="search_complete"
        )

    async def async_step_search_timeout(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Inform the user that no device has been found."""

        if user_input is not None:
            return await self.async_step_wait_for_device()

        return self.async_show_form(
            step_id="search_timeout"
        )

    async def async_step_search_complete(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Create a configuration entry for the Haus-Bus devices."""

        return self.async_create_entry(
            title="Haus-Bus",
            data={},
        )

    async def _async_wait_for_device(self) -> None:
        """Search for devices and wait until one is found."""

        if self.home_server is None:
            self.home_server = await async_acquire_home_server(
                self.hass
            )

        assert self.home_server is not None

        try:
            await self.hass.async_add_executor_job(
                self.home_server.searchDevices
            )

            await asyncio.wait_for(
                self._check_device_found(),
                _DEVICE_SEARCH_TIMEOUT,
            )

        except asyncio.CancelledError:
            _LOGGER.debug(
                "Haus-Bus device search was cancelled"
            )
            raise

    async def _check_device_found(self) -> bool:
        """Check periodically whether a device has been found."""

        assert self.home_server is not None

        while not self.home_server.is_any_device_found():
            await asyncio.sleep(0.1)

        return True