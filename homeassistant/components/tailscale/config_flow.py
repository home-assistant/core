"""Config flow to configure the Tailscale integration."""

from collections.abc import Mapping
from typing import Any, override

from tailscale import Tailscale, TailscaleAuthenticationError, TailscaleError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_OAUTH_CLIENT_ID, CONF_OAUTH_CLIENT_SECRET, CONF_TAILNET, DOMAIN

OAUTH_URL = "https://login.tailscale.com/admin/settings/oauth"

OAUTH_SCHEMA = {
    vol.Required(CONF_OAUTH_CLIENT_ID): str,
    vol.Required(CONF_OAUTH_CLIENT_SECRET): TextSelector(
        config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
    ),
}

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_TAILNET): str, **OAUTH_SCHEMA})

STEP_REAUTH_SCHEMA = vol.Schema(OAUTH_SCHEMA)


async def validate_input(
    hass: HomeAssistant, *, tailnet: str, user_input: Mapping[str, Any]
) -> None:
    """Try using the given tailnet & OAuth credentials against the Tailscale API."""
    session = async_get_clientsession(hass)
    tailscale = Tailscale(
        session=session,
        tailnet=tailnet,
        oauth_client_id=user_input[CONF_OAUTH_CLIENT_ID],
        oauth_client_secret=user_input[CONF_OAUTH_CLIENT_SECRET],
    )
    try:
        await tailscale.devices()
    finally:
        # Requesting an access token schedules a task that expires it; closing
        # cancels it. The session is owned by Home Assistant and left open.
        await tailscale.close()


class TailscaleFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Tailscale."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_TAILNET])
            self._abort_if_unique_id_configured()
            try:
                await validate_input(
                    self.hass,
                    tailnet=user_input[CONF_TAILNET],
                    user_input=user_input,
                )
            except TailscaleAuthenticationError:
                errors["base"] = "invalid_auth"
            except TailscaleError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_TAILNET],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            description_placeholders={"oauth_url": OAUTH_URL},
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
        """Re-authenticate with an OAuth client, migrating an API token entry."""
        errors = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    tailnet=reauth_entry.data[CONF_TAILNET],
                    user_input=user_input,
                )
            except TailscaleAuthenticationError:
                errors["base"] = "invalid_auth"
            except TailscaleError:
                errors["base"] = "cannot_connect"
            else:
                # Replace, rather than update, so a migrated entry's API access
                # token is not left behind in storage.
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={CONF_TAILNET: reauth_entry.data[CONF_TAILNET], **user_input},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={"oauth_url": OAUTH_URL},
            errors=errors,
        )
