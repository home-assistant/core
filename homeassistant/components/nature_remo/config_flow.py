"""Config flow for the Nature Remo integration."""

import logging
from typing import Any, override

from aionatureremo import NatureRemoAuthError, NatureRemoClient, NatureRemoError, User
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_TOKEN_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_TOKEN): str})
TOKEN_URL_PLACEHOLDERS = {"token_url": "https://home.nature.global/"}


class NatureRemoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Nature Remo config flow."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _async_validate(self, token: str) -> tuple[User | None, str | None]:
        """Validate the token, returning the user or an error code."""
        client = NatureRemoClient(token, async_get_clientsession(self.hass))
        try:
            return await client.get_user(), None
        except NatureRemoAuthError:
            return None, "invalid_auth"
        except NatureRemoError as err:
            # cannot_connect covers 429s and transient network trouble; keep a
            # trace so the cause is diagnosable from the log.
            _LOGGER.debug("Token validation failed: %s", err)
            return None, "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating the access token")
            return None, "unknown"

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the personal access token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user, error_code = await self._async_validate(user_input[CONF_API_TOKEN])
            if user is not None:
                await self.async_set_unique_id(user.id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user.nickname, data=user_input)
            if error_code is not None:
                errors["base"] = error_code
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_TOKEN_DATA_SCHEMA,
            errors=errors,
            description_placeholders=TOKEN_URL_PLACEHOLDERS,
        )
