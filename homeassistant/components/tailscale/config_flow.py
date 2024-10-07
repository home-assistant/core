"""Config flow to configure the Tailscale integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tailscale import Tailscale, TailscaleAuthenticationError, TailscaleError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_TAILNET, DOMAIN

AUTHKEYS_URL = "https://login.tailscale.com/admin/settings/keys"


async def validate_input(hass: HomeAssistant, *, tailnet: str, api_key: str) -> None:
    """Try using the give tailnet & api key against the Tailscale API."""
    session = async_get_clientsession(hass)
    tailscale = Tailscale(
        session=session,
        api_key=api_key,
        tailnet=tailnet,
    )
    await tailscale.devices()


class TailscaleFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Tailscale."""

    VERSION = 1

    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    tailnet=user_input[CONF_TAILNET],
                    api_key=user_input[CONF_API_KEY],
                )
            except TailscaleAuthenticationError:
                errors["base"] = "invalid_auth"
            except TailscaleError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_TAILNET])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_TAILNET],
                    data={
                        CONF_TAILNET: user_input[CONF_TAILNET],
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            description_placeholders={"authkeys_url": AUTHKEYS_URL},
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TAILNET, default=user_input.get(CONF_TAILNET, "")
                    ): str,
                    vol.Required(
                        CONF_API_KEY, default=user_input.get(CONF_API_KEY, "")
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with Tailscale."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with Tailscale."""
        errors = {}

        if user_input is not None and self.reauth_entry:
            try:
                await validate_input(
                    self.hass,
                    tailnet=self.reauth_entry.data[CONF_TAILNET],
                    api_key=user_input[CONF_API_KEY],
                )
            except TailscaleAuthenticationError:
                errors["base"] = "invalid_auth"
            except TailscaleError:
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.reauth_entry,
                    data={
                        **self.reauth_entry.data,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"authkeys_url": AUTHKEYS_URL},
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
