"""Config flow for MyQ integration."""
import logging

import pymyq
from pymyq.errors import InvalidCredentialsError, MyQError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MyQ."""

    VERSION = 1

    def __init__(self):
        """Start a myq config flow."""
        self._reauth_unique_id = None

    async def _async_validate_input(self, username, password):
        """Validate the user input allows us to connect."""
        websession = aiohttp_client.async_get_clientsession(self.hass)
        try:
            await pymyq.login(username, password, websession)
        except InvalidCredentialsError:
            return {CONF_PASSWORD: "invalid_auth"}
        except MyQError:
            return {"base": "cannot_connect"}
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}

        return None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            errors = await self._async_validate_input(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        """Handle reauth."""
        self._reauth_unique_id = self.context["unique_id"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauth input."""
        errors = {}
        existing_entry = await self.async_set_unique_id(self._reauth_unique_id)
        if user_input is not None:
            errors = await self._async_validate_input(
                existing_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if not errors:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: existing_entry.data[CONF_USERNAME]
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
