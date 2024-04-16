"""Config flow for A. O. Smith integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from py_aosmith import AOSmithAPIClient, AOSmithInvalidCredentialsException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AOSmithConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for A. O. Smith."""

    VERSION = 1

    _reauth_email: str | None = None

    async def _async_validate_credentials(
        self, email: str, password: str
    ) -> str | None:
        """Validate the credentials. Return an error string, or None if successful."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        client = AOSmithAPIClient(email, password, session)

        try:
            await client.get_devices()
        except AOSmithInvalidCredentialsException:
            return "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return "unknown"

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            unique_id = user_input[CONF_EMAIL].lower()
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            error = await self._async_validate_credentials(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if error is None:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

            errors["base"] = error

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

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth if the user credentials have changed."""
        self._reauth_email = entry_data[CONF_EMAIL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user's reauth credentials."""
        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_email is not None:
            email = self._reauth_email
            password = user_input[CONF_PASSWORD]
            entry_id = self.context["entry_id"]

            if entry := self.hass.config_entries.async_get_entry(entry_id):
                error = await self._async_validate_credentials(email, password)
                if error is None:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data=entry.data | user_input,
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")
                errors["base"] = error

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={CONF_EMAIL: self._reauth_email},
            errors=errors,
        )
