"""Config flow to configure the Tailscale integration."""

from collections.abc import Mapping
from typing import Any, override

from tailscale import Tailscale, TailscaleAuthenticationError, TailscaleError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_OAUTH_CLIENT_ID, CONF_OAUTH_CLIENT_SECRET, CONF_TAILNET, DOMAIN

AUTHKEYS_URL = "https://login.tailscale.com/admin/settings/keys"
OAUTH_URL = "https://login.tailscale.com/admin/settings/oauth"

SECRET_SELECTOR = TextSelector(
    config=TextSelectorConfig(type=TextSelectorType.PASSWORD)
)

STEP_OAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OAUTH_CLIENT_ID): str,
        vol.Required(CONF_OAUTH_CLIENT_SECRET): SECRET_SELECTOR,
    }
)
STEP_API_KEY_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): SECRET_SELECTOR})


def _credentials(user_input: Mapping[str, Any]) -> dict[str, Any]:
    """Return the client credentials contained in the given user input."""
    if CONF_OAUTH_CLIENT_ID in user_input:
        return {
            "oauth_client_id": user_input[CONF_OAUTH_CLIENT_ID],
            "oauth_client_secret": user_input[CONF_OAUTH_CLIENT_SECRET],
        }
    return {"api_key": user_input[CONF_API_KEY]}


async def validate_input(
    hass: HomeAssistant, *, tailnet: str, user_input: Mapping[str, Any]
) -> None:
    """Try using the given tailnet & credentials against the Tailscale API."""
    session = async_get_clientsession(hass)
    tailscale = Tailscale(
        session=session,
        tailnet=tailnet,
        **_credentials(user_input),
    )
    try:
        await tailscale.devices()
    finally:
        # Using OAuth schedules a task that expires the access token; closing
        # cancels it. The session is owned by Home Assistant and left open.
        await tailscale.close()


class TailscaleFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Tailscale."""

    VERSION = 1

    tailnet: str

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self.tailnet = user_input[CONF_TAILNET]
            await self.async_set_unique_id(self.tailnet)
            self._abort_if_unique_id_configured()
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_TAILNET): str}),
        )

    async def async_step_credentials(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick how to authenticate with Tailscale."""
        return self.async_show_menu(
            step_id="credentials", menu_options=["oauth", "api_key"]
        )

    async def async_step_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure an OAuth client. OAuth clients do not expire."""
        return await self._async_create_with_credentials(
            "oauth", STEP_OAUTH_SCHEMA, {"oauth_url": OAUTH_URL}, user_input
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure an API access token. These expire after 90 days."""
        return await self._async_create_with_credentials(
            "api_key", STEP_API_KEY_SCHEMA, {"authkeys_url": AUTHKEYS_URL}, user_input
        )

    async def _async_create_with_credentials(
        self,
        step_id: str,
        data_schema: vol.Schema,
        description_placeholders: dict[str, str],
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate the given credentials and create the config entry."""
        errors = {}

        if user_input is not None:
            try:
                await validate_input(
                    self.hass, tailnet=self.tailnet, user_input=user_input
                )
            except TailscaleAuthenticationError:
                errors["base"] = "invalid_auth"
            except TailscaleError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self.tailnet,
                    data={CONF_TAILNET: self.tailnet, **user_input},
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            description_placeholders=description_placeholders,
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
        """Handle re-authentication of an API access token."""
        if CONF_OAUTH_CLIENT_ID in self._get_reauth_entry().data:
            return await self.async_step_reauth_confirm_oauth(user_input)

        return await self._async_reauth_form(
            "reauth_confirm",
            STEP_API_KEY_SCHEMA,
            {"authkeys_url": AUTHKEYS_URL},
            user_input,
        )

    async def async_step_reauth_confirm_oauth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication of an OAuth client."""
        return await self._async_reauth_form(
            "reauth_confirm_oauth",
            STEP_OAUTH_SCHEMA,
            {"oauth_url": OAUTH_URL},
            user_input,
        )

    async def _async_reauth_form(
        self,
        step_id: str,
        data_schema: vol.Schema,
        description_placeholders: dict[str, str],
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Validate re-entered credentials and update the entry."""
        reauth_entry = self._get_reauth_entry()
        errors = {}

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
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Migrate an existing entry to OAuth client credentials."""
        reconfigure_entry = self._get_reconfigure_entry()
        errors = {}

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    tailnet=reconfigure_entry.data[CONF_TAILNET],
                    user_input=user_input,
                )
            except TailscaleAuthenticationError:
                errors["base"] = "invalid_auth"
            except TailscaleError:
                errors["base"] = "cannot_connect"
            else:
                # Replace, rather than update, so a previously configured API
                # access token is not left behind in the entry.
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_TAILNET: reconfigure_entry.data[CONF_TAILNET],
                        **user_input,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_OAUTH_SCHEMA,
            description_placeholders={"oauth_url": OAUTH_URL},
            errors=errors,
        )
