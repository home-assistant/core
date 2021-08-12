"""Config flow for Mazda Connected Services integration."""
import logging

import aiohttp
from pymazda import (
    Client as MazdaAPI,
    MazdaAccountLockedException,
    MazdaAuthenticationException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_REGION
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN, MAZDA_REGIONS

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_REGION): vol.In(MAZDA_REGIONS),
    }
)


class MazdaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mazda Connected Services."""

    VERSION = 1

    def __init__(self):
        """Start the mazda config flow."""
        self._reauth_entry = None
        self._email = None
        self._region = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._region = user_input[CONF_REGION]
            unique_id = user_input[CONF_EMAIL].lower()
            await self.async_set_unique_id(unique_id)
            if not self._reauth_entry:
                self._abort_if_unique_id_configured()
            websession = aiohttp_client.async_get_clientsession(self.hass)
            mazda_client = MazdaAPI(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input[CONF_REGION],
                websession,
            )

            try:
                await mazda_client.validate_credentials()
            except MazdaAuthenticationException:
                errors["base"] = "invalid_auth"
            except MazdaAccountLockedException:
                errors["base"] = "account_locked"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception as ex:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(
                    "Unknown error occurred during Mazda login request: %s", ex
                )
            else:
                if not self._reauth_entry:
                    return self.async_create_entry(
                        title=user_input[CONF_EMAIL], data=user_input
                    )
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input, unique_id=unique_id
                )
                # Reload the config entry otherwise devices will remain unavailable
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL, default=self._email): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_REGION, default=self._region): vol.In(
                        MAZDA_REGIONS
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth if the user credentials have changed."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._email = user_input[CONF_EMAIL]
        self._region = user_input[CONF_REGION]
        return await self.async_step_user()
