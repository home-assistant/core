"""Config flow to configure the Tailscale integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tailscale import Tailscale, TailscaleAuthenticationError, TailscaleError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
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
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with Tailscale."""
        errors = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            try:
                await validate_input(
                    self.hass,
                    tailnet=reauth_entry.data[CONF_TAILNET],
                    api_key=user_input[CONF_API_KEY],
                )
            except TailscaleAuthenticationError:
                errors["base"] = "invalid_auth"
            except TailscaleError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"authkeys_url": AUTHKEYS_URL},
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
