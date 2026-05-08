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

from . import register_webhook
from .const import DOMAIN
from .devices import devices

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
                register(devices, self.device)
            except CCLDeviceRegistrationException:
                _LOGGER.debug(
                    "Device with webhook ID %s is already registered",
                    self.webhook_id,
                )
                self.device = devices[self.webhook_id]
            # Try to register the webhook
            try:
                await register_webhook(self.hass, self.webhook_id)
            except (ValueError, NoURLAvailableError) as err:
                _LOGGER.error("Failed to register webhook: %s", err)
                return self.async_abort(reason="invalid_webhook")
            _LOGGER.debug("Webhook registered at hass: %s", self.webhook_id)

        # Create a task to wait for the first update from the device
        if not self.task_one:

            async def check_task() -> None:
                async def _wait_for_update() -> None:
                    assert self.device is not None
                    while self.device.last_update_time is None:
                        await asyncio.sleep(1)
                    assert self.device.device_id is not None
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
                _LOGGER.error("Timed out waiting for device update during config flow")
                self.task_one = None
                webhook.async_unregister(self.hass, self.webhook_id)
                devices.pop(self.webhook_id, None)
                return self.async_abort(reason="connect_timeout")
            except AbortFlow:
                _LOGGER.debug("Device already configured during config flow")
                self.task_one = None
                webhook.async_unregister(self.hass, self.webhook_id)
                devices.pop(self.webhook_id, None)
                return self.async_abort(reason="already_configured")

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

    def async_remove(self) -> None:
        """Clean up when config flow is cancelled or removed."""
        # Cancel the task if it's still running
        if self.task_one and not self.task_one.done():
            self.task_one.cancel()

        # Unregister the webhook
        if CONF_WEBHOOK_ID in self.data:
            webhook.async_unregister(self.hass, self.data[CONF_WEBHOOK_ID])

        # Remove the device from the global devices dict
        if CONF_WEBHOOK_ID in self.data:
            devices.pop(self.data[CONF_WEBHOOK_ID], None)
