"""Config flow for CCL Electronics."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any

from aioccl import CCLDevice, CCLServer
from aioccl.exception import CCLDeviceRegistrationException
from aiohttp import web
from aiohttp.hdrs import METH_POST
from yarl import URL

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import progress_step
from homeassistant.helpers.network import get_url

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class CCLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    data: dict[str, Any] = {}
    device: CCLDevice
    task_one: asyncio.Task | None = None

    @progress_step(
        description_placeholders=lambda self: {
            CONF_HOST: self.data[CONF_HOST],
            CONF_PORT: self.data[CONF_PORT],
            CONF_PATH: self.data[CONF_PATH],
        }
    )
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        uncompleted_task: asyncio.Task[None] | None = None

        if len(self.data) == 0:
            self.data[CONF_WEBHOOK_ID] = DOMAIN + secrets.token_hex(4)

            url = URL(get_url(self.hass, prefer_cloud=True))
            assert url.host

            self.data[CONF_HOST] = url.host
            self.data[CONF_PORT] = str(url.port)
            self.data[CONF_PATH] = webhook.async_generate_path(
                self.data[CONF_WEBHOOK_ID]
            )

            await self.async_set_unique_id(self.data[CONF_WEBHOOK_ID])
            self._abort_if_unique_id_configured()

            self.device = CCLDevice(self.data[CONF_WEBHOOK_ID])
            try:
                CCLServer.register(self.device)
            except CCLDeviceRegistrationException:
                _LOGGER.debug(
                    "Device with webhook ID %s is already registered",
                    self.data[CONF_WEBHOOK_ID],
                )
                self.device = CCLServer.devices[self.data[CONF_WEBHOOK_ID]]

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

        if not self.task_one:

            async def check_task() -> None:
                while self.device.last_update_time is None:
                    await asyncio.sleep(1)

            self.task_one = self.hass.async_create_task(check_task())

        if not self.task_one.done():
            progress_action = "task_one"
            uncompleted_task = self.task_one

        if uncompleted_task:
            return self.async_show_progress(
                progress_action=progress_action,
                progress_task=uncompleted_task,
            )

        self.async_update_progress(1)
        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the final step."""
        if user_input is not None:
            return self.async_create_entry(
                title="CCL Weather Station",
                data={
                    CONF_WEBHOOK_ID: self.data[CONF_WEBHOOK_ID],
                    CONF_HOST: self.data[CONF_HOST],
                    CONF_PORT: self.data[CONF_PORT],
                },
            )
        return self.async_show_form(step_id="finish")
