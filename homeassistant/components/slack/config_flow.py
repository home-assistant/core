"""Config flow for Slack integration."""
from __future__ import annotations

import logging

from slack import WebClient
from slack.errors import SlackApiError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_ICON, CONF_NAME, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
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


class SlackFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Slack."""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
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

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        _LOGGER.warning(
            "Configuration of the Slack integration in YAML is deprecated and "
            "will be removed in a future release; Your existing configuration "
            "has been imported into the UI automatically and can be safely removed "
            "from your configuration.yaml file"
        )
        entries = self._async_current_entries()
        if any(x.data[CONF_API_KEY] == import_config[CONF_API_KEY] for x in entries):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)

    async def _async_try_connect(
        self, token: str
    ) -> tuple[str, None] | tuple[None, dict[str, str]]:
        """Try connecting to Slack."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        client = WebClient(token=token, run_async=True, session=session)

        try:
            info = await client.auth_test()
        except SlackApiError as ex:
            if ex.response["error"] == "invalid_auth":
                return "invalid_auth", None
            return "cannot_connect", None
        except Exception as ex:  # pylint:disable=broad-except
            _LOGGER.exception("Unexpected exception: %s", ex)
            return "unknown", None
        return None, info
