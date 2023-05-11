"""Twitch configuration flow."""
import logging
from typing import Any

from twitchAPI.twitch import (
    InvalidTokenException,
    MissingScopeException,
    Twitch,
    TwitchAuthorizationException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, OAUTH_SCOPES

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        # vol.Required(CONF_CHANNELS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_TOKEN): cv.string,
    }
)


class TwitchConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Twitch config flow."""

    VERSION = 1

    def _show_setup_form(self, user_input=None, errors=None) -> FlowResult:
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                    vol.Optional(CONF_TOKEN): cv.string,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""

        if user_input is None:
            return self._show_setup_form(user_input, errors=None)

        # Check if already configured
        if self.unique_id is None:
            await self.async_set_unique_id(user_input[CONF_CLIENT_ID])
            self._abort_if_unique_id_configured()

        try:
            await self.hass.async_add_executor_job(_attempt_login, user_input)
        except MissingScopeException:
            _LOGGER.error("OAuth token is missing required scope")
            return self._show_setup_form(user_input, {"base": "invalid_auth"})
        except TwitchAuthorizationException:
            _LOGGER.error("Invalid client ID or client secret")
            return self._show_setup_form(user_input, {"base": "invalid_auth"})
        except InvalidTokenException:
            _LOGGER.error("OAuth token is invalid")
            return self._show_setup_form(user_input, {"base": "invalid_auth"})

        return self.async_create_entry(title="Twitch", data=user_input)

    async def async_step_import(
        self, import_info: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle import from legacy config."""
        return await self.async_step_user(import_info)


def _attempt_login(user_input: dict[str, Any]):
    client_id: str = user_input[CONF_CLIENT_ID]
    client_secret: str = user_input[CONF_CLIENT_SECRET]
    oauth_token: str | None = user_input.get(CONF_TOKEN)

    client = Twitch(
        app_id=client_id,
        app_secret=client_secret,
        target_app_auth_scope=OAUTH_SCOPES,
    )

    client.auto_refresh_auth = False

    if oauth_token:
        client.set_user_authentication(
            token=oauth_token, scope=OAUTH_SCOPES, validate=True
        )
