"""Config flow for the WebDAV integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import yarl

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import slugify

from .const import CONF_BACKUP_PATH, DOMAIN
from .helpers import async_create_client

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.URL,
            )
        ),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
            )
        ),
        vol.Optional(CONF_BACKUP_PATH, default="/"): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)


class WebDavConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WebDAV."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = async_create_client(
                hass=self.hass,
                url=user_input[CONF_URL],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                verify_ssl=user_input.get(CONF_VERIFY_SSL, True),
            )

            # Check if we can connect to the WebDAV server
            # .check() already does error handling and will return True
            # if we can access the root directory
            if await client.check():
                parsed_url = yarl.URL(user_input[CONF_URL])
                unq_id = f"{user_input[CONF_USERNAME]}@{parsed_url.host}"

                await self.async_set_unique_id(slugify(unq_id))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=unq_id, data=user_input)

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
