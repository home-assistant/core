"""Config flow for Klyqa."""
from __future__ import annotations

import asyncio
from typing import Any

from klyqa_ctl import klyqa_ctl as api
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, LOGGER

user_step_data_schema = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

NoneType = type(None)


class KlyqaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    # (this is not implemented yet)
    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""

    async def _show_setup_form(
        self,
        errors: dict[Any, Any] | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> FlowResult:
        """Show the setup form to the user."""

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=username): cv.string,
                    vol.Required(CONF_PASSWORD, default=password): cv.string,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if (
            self.hass
            and DOMAIN in self.hass.data
            and len(self.hass.data[DOMAIN].entries)
        ):
            # already logged in from platform or other way
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return await self._show_setup_form()

        username = str(user_input[CONF_USERNAME])
        password = str(user_input[CONF_PASSWORD])

        return await self._async_klyqa_login(
            step_id="user", username=username, password=password
        )

    async def _async_klyqa_login(
        self, step_id: str, username: str, password: str
    ) -> FlowResult:
        """Handle login with Klyqa."""
        errors = {}
        klyqa: api.Klyqa_account | None = None
        try:

            klyqa = api.Klyqa_account(None, username, password)

            login = self.hass.async_run_job(
                klyqa.login,
            )
            if login:
                await asyncio.wait_for(login, timeout=30)
            else:
                raise Exception()

            if not klyqa or not klyqa.access_token or not login:
                raise ValueError()

        except (ConnectTimeout, HTTPError, ValueError) as exception:
            LOGGER.error("Unable to connect to Klyqa: %s", exception)
            errors = {"base": "cannot_connect"}

        if errors:
            return await self._show_setup_form(errors, username, password)

        return await self._async_create_entry(username, password)

    async def _async_create_entry(self, username: str, password: str) -> FlowResult:
        """Create the config entry."""

        config_data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
        }
        existing_entry = await self.async_set_unique_id(username)

        if existing_entry:
            self.hass.config_entries.async_update_entry(
                existing_entry, data=config_data
            )
            # Reload the Klyqa config entry otherwise devices will remain unavailable
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(title=username, data=config_data)
