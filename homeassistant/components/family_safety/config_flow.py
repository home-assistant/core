"""Config flow for the Microsoft Family Safety integration."""

from __future__ import annotations

import logging
from typing import Any

from pyfamilysafety import Authenticator
from pyfamilysafety.exceptions import Unauthorized
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGIN_LINK

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})


class FamilySafetyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microsoft Family Safety."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                auth = await Authenticator.create(
                    token=user_input[CONF_API_TOKEN],
                    use_refresh_token=False,
                    client_session=async_get_clientsession(self.hass),
                )
                await self.async_set_unique_id(auth.user_id)
                self._abort_if_unique_id_configured()
            except Unauthorized as err:
                _LOGGER.error(err)
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=auth.user_id, data={CONF_API_TOKEN: auth.refresh_token}
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"link": LOGIN_LINK},
        )
