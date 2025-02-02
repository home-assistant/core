"""Adds config flow for SabNzbd."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import yarl

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import DOMAIN
from .helpers import get_client

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
            )
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            )
        ),
    }
)


class SABnzbdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sabnzbd config flow."""

    VERSION = 1

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration flow."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            sab_api = await get_client(self.hass, user_input)
            if not sab_api:
                errors["base"] = "cannot_connect"
            else:
                self._async_abort_entries_match(
                    {
                        CONF_URL: user_input[CONF_URL],
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    }
                )

                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data_updates=user_input
                    )

                parsed_url = yarl.URL(user_input[CONF_URL])
                return self.async_create_entry(
                    title=slugify(parsed_url.host), data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                self._get_reconfigure_entry().data
                if self.source == SOURCE_RECONFIGURE
                else user_input,
            ),
            errors=errors,
        )
