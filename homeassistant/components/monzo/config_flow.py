"""Config flow for Monzo."""

import asyncio
from collections.abc import Mapping
import logging
from typing import Any, override

from aiohttp import ClientError
from monzopy import AuthorisationExpiredError, InvalidMonzoAPIResponseError

from homeassistant.components.webhook import async_generate_id
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_TOKEN, CONF_WEBHOOK_ID
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MonzoAPI
from .const import DOMAIN

APPROVAL_POLL_INTERVAL = 5
APPROVAL_TIMEOUT = 300


class MonzoFlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow."""

    DOMAIN = DOMAIN
    VERSION = 1
    MINOR_VERSION = 3

    oauth_data: dict[str, Any]
    approval_task: asyncio.Task[None] | None = None

    @property
    @override
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def _async_wait_for_approval(self) -> None:
        """Wait for the user to approve access in the Monzo app."""
        api = MonzoAPI(
            async_get_clientsession(self.hass),
            self.oauth_data[CONF_TOKEN]["access_token"],
        )

        async with asyncio.timeout(APPROVAL_TIMEOUT):
            while True:
                try:
                    await api.user_account.accounts()
                except AuthorisationExpiredError:
                    await asyncio.sleep(APPROVAL_POLL_INTERVAL)
                else:
                    return

    async def async_step_wait_for_approval(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for in-app approval."""
        if self.approval_task is None:
            self.approval_task = self.hass.async_create_task(
                self._async_wait_for_approval()
            )

        if not self.approval_task.done():
            return self.async_show_progress(
                step_id="wait_for_approval",
                progress_action="wait_for_approval",
                progress_task=self.approval_task,
            )

        try:
            await self.approval_task
        except TimeoutError:
            return self.async_show_progress_done(next_step_id="approval_timeout")
        except ClientError, InvalidMonzoAPIResponseError:
            return self.async_show_progress_done(next_step_id="connection_error")
        finally:
            self.approval_task = None

        return self.async_show_progress_done(next_step_id="finish_approval")

    async def async_step_approval_timeout(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle an approval timeout."""
        if user_input is not None:
            return await self.async_step_wait_for_approval()

        self._set_confirm_only()
        return self.async_show_form(step_id="approval_timeout")

    async def async_step_connection_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a connection error while waiting for approval."""
        if user_input is not None:
            return await self.async_step_wait_for_approval()

        self._set_confirm_only()
        return self.async_show_form(step_id="connection_error")

    async def async_step_finish_approval(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish setup after in-app approval."""
        if self.source != SOURCE_REAUTH:
            return self.async_create_entry(
                title=DOMAIN,
                data={**self.oauth_data, CONF_WEBHOOK_ID: async_generate_id()},
            )
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates=self.oauth_data,
        )

    @override
    async def async_oauth_create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        """Create an entry for the flow."""
        self.oauth_data = data
        user_id = data[CONF_TOKEN]["user_id"]
        await self.async_set_unique_id(str(user_id))
        if self.source != SOURCE_REAUTH:
            self._abort_if_unique_id_configured()
        else:
            self._abort_if_unique_id_mismatch(reason="wrong_account")

        return await self.async_step_wait_for_approval()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
