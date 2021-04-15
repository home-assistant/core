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
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
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
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input=None):
        """Perform reauth if the user credentials have changed."""
        errors = {}

        if user_input is not None:
            try:
                websession = aiohttp_client.async_get_clientsession(self.hass)
                mazda_client = MazdaAPI(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_REGION],
                    websession,
                )
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
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())

                for entry in self._async_current_entries():
                    if entry.unique_id == self.unique_id:
                        self.hass.config_entries.async_update_entry(
                            entry, data=user_input
                        )

                        # Reload the config entry otherwise devices will remain unavailable
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(entry.entry_id)
                        )

                        return self.async_abort(reason="reauth_successful")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth", data_schema=DATA_SCHEMA, errors=errors
        )
