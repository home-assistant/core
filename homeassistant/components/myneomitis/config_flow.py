"""Config flow for MyNeomitis integration."""

import logging
from typing import Any

import aiohttp
from pyaxencoapi import PyAxencoAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyNeoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the MyNeomitis integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step of the configuration flow.

        Args:
            user_input: User-provided input from the form, or None if no input is provided.

        Returns:
            FlowResult: The result of the configuration flow step.

        """
        errors: dict[str, str] = {}
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            email: str = user_input["email"]
            password: str = user_input["password"]

            session = async_get_clientsession(self.hass)
            api = PyAxencoAPI("myneomitis", session)

            try:
                await api.login(email, password)

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

            except aiohttp.ClientResponseError as e:
                if e.status == 401:
                    _LOGGER.error("MyNeomitis : Authentication failed: %s", e)
                    errors["base"] = "auth_failed"
                else:
                    _LOGGER.error("MyNeomitis : HTTP error: %s", e)
                    errors["base"] = "connection_error"
            except aiohttp.ClientConnectionError as e:
                _LOGGER.error("MyNeomitis : Connection error: %s", e)
                errors["base"] = "connection_error"
            except aiohttp.ClientError as e:
                _LOGGER.error(
                    "MyNeomitis : Unexpected aiohttp client error during login: %s", e
                )
                errors["base"] = "unknown_error"
            except RuntimeError as e:
                _LOGGER.error("MyNeomitis : Runtime error during login: %s", e)
                errors["base"] = "unknown_error"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("email"): str,
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )
