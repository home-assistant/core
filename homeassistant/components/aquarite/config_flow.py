"""Config Flow for the Aquarite integration."""

from __future__ import annotations

import logging
from typing import Any

from aioaquarite import AquariteAuth, AquariteClient, AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class AquariteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Aquarite config flow (one entry per Hayward account)."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            try:
                auth = AquariteAuth(session, username, password)
                await auth.authenticate()
                api = AquariteClient(auth)
                pools = await api.get_pools()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected error during authentication")
                errors["base"] = "unknown"
            else:
                if not pools:
                    errors["base"] = "no_pools"
                else:
                    return self.async_create_entry(
                        title=username,
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: password,
                        },
                    )

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )
