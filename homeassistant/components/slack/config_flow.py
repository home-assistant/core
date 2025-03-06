"""Config flow for Slack integration."""

from __future__ import annotations

import logging

from slack.errors import SlackApiError
from slack_sdk.web.async_client import AsyncSlackResponse, AsyncWebClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_ICON, CONF_NAME, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import CONF_DEFAULT_CHANNEL, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_DEFAULT_CHANNEL): str,
        vol.Optional(CONF_ICON): str,
        vol.Optional(CONF_USERNAME): str,
    }
)


class SlackFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Slack."""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            error, info = await self._async_try_connect(user_input[CONF_API_KEY])
            if error is not None:
                errors["base"] = error
            elif info is not None:
                await self.async_set_unique_id(info["team_id"].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, info["team"]),
                    data={CONF_NAME: user_input.get(CONF_NAME, info["team"])}
                    | user_input,
                )

        user_input = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors,
        )

    async def _async_try_connect(
        self, token: str
    ) -> tuple[str, None] | tuple[None, AsyncSlackResponse]:
        """Try connecting to Slack."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        client = AsyncWebClient(token=token, session=session)  # No run_async

        try:
            info = await client.auth_test()
        except SlackApiError as ex:
            if ex.response["error"] == "invalid_auth":
                return "invalid_auth", None
            return "cannot_connect", None
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown", None
        return None, info
