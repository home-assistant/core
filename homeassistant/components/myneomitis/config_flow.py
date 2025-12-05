"""Config flow for MyNeomitis integration."""

import logging
from typing import Any

import aiohttp
from pyaxencoapi import PyAxencoAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyNeoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the MyNeomitis integration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email: str = user_input[CONF_EMAIL]
            password: str = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            api = PyAxencoAPI(session)

            try:
                await api.login(email, password)
            except aiohttp.ClientResponseError as e:
                if e.status == 401:
                    errors["base"] = "auth_failed"
                else:
                    errors["base"] = "connection_error"
            except aiohttp.ClientConnectionError:
                errors["base"] = "connection_error"
            except aiohttp.ClientError:
                errors["base"] = "unknown_error"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown_error"

            if not errors:
                # Prevent duplicate configuration with the same user ID
                await self.async_set_unique_id(api.user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"MyNeo ({email})",
                    data={
                        "email": email,
                        "password": password,
                        "token": api.token,
                        "refresh_token": api.refresh_token,
                        "user_id": api.user_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
