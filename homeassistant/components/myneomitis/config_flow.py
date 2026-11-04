"""Config flow for MyNeomitis integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import aiohttp
import probatio
from pyaxencoapi import PyAxencoAPI

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_USER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MyNeoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the configuration flow for the MyNeomitis integration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _async_login(
        self, email: str, password: str
    ) -> tuple[str | None, dict[str, str]]:
        """Log in and return the user ID and errors."""
        errors: dict[str, str] = {}
        session = async_get_clientsession(self.hass)
        api = PyAxencoAPI(session)

        try:
            await api.login(email, password)
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                errors["base"] = "invalid_auth"
            elif e.status >= 500:
                errors["base"] = "cannot_connect"
            else:
                errors["base"] = "unknown"
        except aiohttp.ClientConnectionError:
            errors["base"] = "cannot_connect"
        except aiohttp.ClientError:
            errors["base"] = "unknown"
        except Exception:
            _LOGGER.exception("Unexpected error during login")
            errors["base"] = "unknown"
        else:
            return api.user_id, errors

        return None, errors

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the configuration flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email: str = user_input[CONF_EMAIL]
            password: str = user_input[CONF_PASSWORD]

            user_id, errors = await self._async_login(email, password)

            if not errors:
                # Prevent duplicate configuration with the same user ID
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"MyNeomitis ({email})",
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_USER_ID: user_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_EMAIL): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        email: str = reauth_entry.data[CONF_EMAIL]

        if user_input is not None:
            password: str = user_input[CONF_PASSWORD]

            user_id, errors = await self._async_login(email, password)

            if not errors:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_mismatch()

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            description_placeholders={CONF_EMAIL: email},
            errors=errors,
        )
