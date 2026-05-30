"""Config flow for CCL Electronics."""

import asyncio
import logging
from typing import Any
from urllib.parse import urlsplit

from aioccl import CCLDevice
from aioccl.exception import CCLDeviceRegistrationException
from aioccl.server import register

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.network import NoURLAvailableError

from . import KEY_DEVICES, register_webhook
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CCLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self.device: CCLDevice | None = None
        self.task_one: asyncio.Task | None = None
        self.webhook_id: str = ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        uncompleted_task: asyncio.Task[None] | None = None

        # Initial step, set up the webhook and device
        if CONF_PATH not in self.data:
            self.webhook_id = self.data[CONF_WEBHOOK_ID] = webhook.async_generate_id()

            try:
                webhook_url = webhook.async_generate_url(
                    self.hass,
                    self.webhook_id,
                    allow_ip=True,
                )
            except NoURLAvailableError as err:
                _LOGGER.error("Failed to fetch Home Assistant URL: %s", err)
                return self.async_abort(reason="invalid_host")

            res = urlsplit(webhook_url)
            port = res.port or (443 if res.scheme == "https" else 80)
            self.data[CONF_HOST] = res.hostname
            self.data[CONF_PORT] = str(port)
            self.data[CONF_PATH] = webhook.async_generate_path(self.webhook_id)

            self.device = CCLDevice(self.webhook_id)
            # Try to register the device, but if it already exists, use the existing one
            try:
                register(self.hass.data.setdefault(KEY_DEVICES, {}), self.device)
            except CCLDeviceRegistrationException:
                _LOGGER.debug(
                    "Device with webhook ID %s is already registered",
                    self.webhook_id,
                )
                self.device = self.hass.data[KEY_DEVICES][self.webhook_id]
            # Try to register the webhook
            try:
                register_webhook(self.hass, self.webhook_id)
            except ValueError as err:
                _LOGGER.error("Failed to register webhook: %s", err)
                self.hass.data[KEY_DEVICES].pop(self.webhook_id, None)
                self.data = {}
                self.webhook_id = ""
                return self.async_abort(reason="invalid_webhook")
            _LOGGER.debug("Webhook registered at hass: %s", self.webhook_id)

        # Create a task to wait for the first update from the device
        if not self.task_one:

            async def check_task() -> None:
                async def _wait_for_update() -> None:
                    if self.device is None:
                        raise AbortFlow("unknown")
                    while self.device.last_update_time is None:
                        await asyncio.sleep(1)
                    if self.device.device_id is None:
                        raise AbortFlow("unknown")
                    await self.async_set_unique_id(self.device.device_id)
                    self._abort_if_unique_id_configured()

                # Avoid a background task that can run indefinitely.
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
            except TimeoutError:
                self.task_one = None
                webhook.async_unregister(self.hass, self.webhook_id)
                self.hass.data[KEY_DEVICES].pop(self.webhook_id, None)
                self.data["abort_reason"] = "connect_timeout"
                _LOGGER.error(
                    "Device with webhook ID %s timed out waiting for update during config flow",
                    self.webhook_id,
                )
                return self.async_show_progress_done(next_step_id="finish")
            except asyncio.CancelledError:
                self.task_one = None
                webhook.async_unregister(self.hass, self.webhook_id)
                self.hass.data[KEY_DEVICES].pop(self.webhook_id, None)
                self.data["abort_reason"] = "unknown"
                _LOGGER.debug(
                    "Device with webhook ID %s config flow task was cancelled",
                    self.webhook_id,
                )
                return self.async_show_progress_done(next_step_id="finish")
            except AbortFlow as err:
                self.task_one = None
                webhook.async_unregister(self.hass, self.webhook_id)
                self.hass.data[KEY_DEVICES].pop(self.webhook_id, None)
                if err.reason == "already_configured":
                    self.data["abort_reason"] = "already_configured"
                    _LOGGER.debug(
                        "Device with webhook ID %s already configured during config flow",
                        self.webhook_id,
                    )
                else:
                    self.data["abort_reason"] = "unknown"
                    _LOGGER.error(
                        "Unknown error occurred for webhook ID %s during config flow",
                        self.webhook_id,
                    )
                return self.async_show_progress_done(next_step_id="finish")

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

        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the final step."""
        # If an abort reason was set during progress, abort now.
        abort_reason = self.data.pop("abort_reason", None)
        if abort_reason is not None:
            return self.async_abort(reason=abort_reason)

        return self.async_create_entry(
            title="CCL Weather Station",
            data={
                CONF_WEBHOOK_ID: self.data[CONF_WEBHOOK_ID],
                CONF_HOST: self.data[CONF_HOST],
                CONF_PORT: self.data[CONF_PORT],
            },
        )

    def async_remove(self) -> None:
        """Clean up when config flow is cancelled or removed."""
        # Cancel the task if it's still running
        if self.task_one and not self.task_one.done():
            self.task_one.cancel()

        # Unregister the webhook and remove the device
        webhook_id = self.data.get(CONF_WEBHOOK_ID)
        if webhook_id:
            webhook.async_unregister(self.hass, webhook_id)
            self.hass.data[KEY_DEVICES].pop(webhook_id, None)
