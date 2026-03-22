"""Config flow for CCL Electronics."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any

from aioccl import CCLDevice, CCLServer
from aioccl.exception import CCLDeviceRegistrationException
from aioccl.server import register
from aiohttp import web
from aiohttp.hdrs import METH_POST
from yarl import URL

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from . import devices
from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class CCLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.device: CCLDevice | None = None
        self.task_one: asyncio.Task | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        uncompleted_task: asyncio.Task[None] | None = None

        # Initial step, set up the webhook and device
        if CONF_PATH not in self.data:
            # Generate a unique webhook ID
            while True:
                self.data[CONF_WEBHOOK_ID] = secrets.token_hex(4)
                if await self.async_set_unique_id(self.data[CONF_WEBHOOK_ID]) is None:
                    break

            url = URL(get_url(self.hass))
            assert url.host

            self.data[CONF_HOST] = url.host
            self.data[CONF_PORT] = str(url.port)
            self.data[CONF_PATH] = webhook.async_generate_path(
                self.data[CONF_WEBHOOK_ID]
            )

            self.device = CCLDevice(self.data[CONF_WEBHOOK_ID])
            # Try to register the device, but if it already exists, use the existing one
            try:
                register(devices, self.device)
            except CCLDeviceRegistrationException:
                _LOGGER.debug(
                    "Device with webhook ID %s is already registered",
                    self.data[CONF_WEBHOOK_ID],
                )
                self.device = devices[self.data[CONF_WEBHOOK_ID]]

            async def register_webhook() -> None:
                """Register webhook for the device."""

                def handle_webhook(
                    hass: HomeAssistant, webhook_id: str, request: web.Request
                ) -> Any:
                    """Handle incoming requests from CCL devices."""
                    return CCLServer.handler(request)

                try:
                    webhook_url = webhook.async_generate_url(
                        self.hass,
                        self.data[CONF_WEBHOOK_ID],
                        allow_ip=True,
                    )

                    webhook.async_register(
                        self.hass,
                        DOMAIN,
                        f"{NAME}-{CONF_WEBHOOK_ID}",
                        self.data[CONF_WEBHOOK_ID],
                        handle_webhook,
                        allowed_methods=[METH_POST],
                    )
                    _LOGGER.debug("Webhook registered at hass: %s", webhook_url)

                except ValueError as err:
                    _LOGGER.error("Failed to register webhook: %s", err)

            await register_webhook()

        # Create a task to wait for the first update from the device
        if not self.task_one:

            async def check_task() -> None:
                assert self.device is not None

                async def _wait_for_update() -> None:
                    while self.device is not None and self.device.last_update_time is None:
                        await asyncio.sleep(1)

                # Limit how long we wait for the device to send an update to
                # avoid a background task that can run indefinitely.
                await asyncio.wait_for(_wait_for_update(), timeout=300)

            self.task_one = self.hass.async_create_task(check_task())

        if not self.task_one.done():
            progress_action = "task_one"
            uncompleted_task = self.task_one
        else:
            # The task has completed; check if it finished successfully or
            # timed out while waiting for the device to send an update.
            try:
                await self.task_one
            except asyncio.TimeoutError:
                _LOGGER.error("Timed out waiting for device update during config flow")
                self.task_one = None
                return self.async_abort(reason="cannot_connect")

        if uncompleted_task:
            return self.async_show_progress(
                step_id="user",
                progress_action=progress_action,
                progress_task=uncompleted_task,
                description_placeholders={
                    CONF_HOST: self.data[CONF_HOST],
                    CONF_PORT: self.data[CONF_PORT],
                    CONF_PATH: self.data[CONF_PATH],
                },
            )

        self.async_update_progress(1)
        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the final step."""
        return self.async_create_entry(
            title="CCL Weather Station",
            data={
                CONF_WEBHOOK_ID: self.data[CONF_WEBHOOK_ID],
                CONF_HOST: self.data[CONF_HOST],
                CONF_PORT: self.data[CONF_PORT],
            },
        )
