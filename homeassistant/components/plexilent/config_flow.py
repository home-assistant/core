"""Config flow for the Plexilent integration."""

import logging
from typing import Any, override

import probatio
from pyplexilent import Plexilent, PlexilentAuthError, PlexilentConnectionError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class PlexilentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Sign in with the Plexilent app account; only the refresh token is kept."""

    VERSION = 1

    async def _login(
        self, email: str, password: str
    ) -> tuple[str | None, dict[str, str]]:
        """Sign in; return the refresh token, or the form errors."""
        try:
            token = await Plexilent(async_get_clientsession(self.hass)).login(
                email, password
            )
        except PlexilentAuthError:
            return None, {"base": "invalid_auth"}
        except PlexilentConnectionError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected error signing in")
            return None, {"base": "unknown"}
        return token, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the app email and password."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip().lower()
            await self.async_set_unique_id(email)
            self._abort_if_unique_id_configured()
            token, errors = await self._login(email, user_input[CONF_PASSWORD])
            if token:
                return self.async_create_entry(
                    title=email,
                    data={CONF_EMAIL: email, CONF_REFRESH_TOKEN: token},
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )
