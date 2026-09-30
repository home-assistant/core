"""Config flow for the Marketplace."""

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from aiogithubapi import (
    GitHubDeviceAPI,
    GitHubException,
    GitHubLoginDeviceModel,
    GitHubLoginOauthModel,
)
from aiogithubapi.common.const import OAUTH_USER_LOGIN
import probatio

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import aiohttp_client

from .const import CLIENT_ID, CLIENT_NAME, DOMAIN
from .utils.logger import LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# GitHub can answer this right after a quick approval, a later poll then gets
# the token, see https://github.com/cli/cli/issues/9302
INVALID_DEVICE_CODE = "The device_code provided is not valid."
ACTIVATION_ATTEMPTS = 3


class MarketplaceConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the Marketplace."""

    VERSION = 1

    hass: HomeAssistant
    activation_task: asyncio.Task | None = None
    device: GitHubDeviceAPI | None = None

    _registration: GitHubLoginDeviceModel | None = None
    _activation: GitHubLoginOauthModel | None = None

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up the Marketplace, browsing needs no GitHub account."""
        return self.async_create_entry(title="", data={})

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Connect a GitHub account, started from the Marketplace panel."""
        return await self.async_step_device(None)

    async def async_step_device(
        self, _user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        """Wait for the user to enter the code on GitHub."""
        if not self.device:
            self.device = GitHubDeviceAPI(
                client_id=CLIENT_ID,
                session=aiohttp_client.async_get_clientsession(self.hass),
                client_name=CLIENT_NAME,
            )
            try:
                response = await self.device.register()
                self._registration = response.data
                LOGGER.debug(
                    "Registered with GitHub for flow %s, waiting for the code",
                    self.flow_id,
                )
            except GitHubException as exception:
                LOGGER.error("Could not register with GitHub: %s", exception)
                return self.async_abort(reason="could_not_register")

        device = self.device
        if (registration := self._registration) is None:
            return self.async_abort(reason="could_not_register")

        async def _wait_for_activation() -> None:
            for attempt in range(1, ACTIVATION_ATTEMPTS + 1):
                try:
                    activation = await device.activation(
                        device_code=registration.device_code
                    )
                except GitHubException as exception:
                    if (
                        str(exception) != INVALID_DEVICE_CODE
                        or attempt == ACTIVATION_ATTEMPTS
                    ):
                        raise
                    LOGGER.debug(
                        "GitHub does not know the device code yet, asking again"
                    )
                    await asyncio.sleep(registration.interval)
                    continue

                self._activation = activation.data
                return

        if self.activation_task is None:
            LOGGER.debug("Waiting for the GitHub activation of flow %s", self.flow_id)
            self.activation_task = self.hass.async_create_task(_wait_for_activation())

        if self.activation_task.done():
            if (task_exception := self.activation_task.exception()) is not None:
                LOGGER.error(
                    "Connecting GitHub failed for flow %s: %s",
                    self.flow_id,
                    task_exception,
                )
                return self.async_show_progress_done(next_step_id="activation_failed")
            return self.async_show_progress_done(next_step_id="device_done")

        return self.async_show_progress(
            step_id="device",
            progress_action="wait_for_device",
            description_placeholders={
                "url": OAUTH_USER_LOGIN,
                "code": registration.user_code,
            },
            progress_task=self.activation_task,
        )

    async def async_step_device_done(
        self, user_input: dict[str, bool] | None = None
    ) -> ConfigFlowResult:
        """Store the token GitHub handed out, and reload the entry."""
        if (activation := self._activation) is None:
            return self.async_abort(reason="could_not_register")

        entry = (
            self._get_reauth_entry()
            if self.source == SOURCE_REAUTH
            else self._get_reconfigure_entry()
        )
        return self.async_update_reload_and_abort(
            entry, data_updates={CONF_TOKEN: activation.access_token}
        )

    async def async_step_activation_failed(
        self, _user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an activation GitHub did not complete."""
        return self.async_abort(reason="activation_failed")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=probatio.Schema({}),
            )
        return await self.async_step_device(None)
