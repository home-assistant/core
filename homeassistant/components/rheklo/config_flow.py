"""Config flow for Rheklo integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiokem import AioKem, AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONNECTION_EXCEPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RhekloConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rheklo."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, token_subject = await self._async_validate_or_error(user_input)
            if not errors:
                await self.async_set_unique_id(token_subject)
                self._abort_if_unique_id_configured()
                email: str = user_input[CONF_EMAIL]
                normalized_email = email.lower()
                return self.async_create_entry(title=normalized_email, data=user_input)

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

    async def _async_validate_or_error(
        self, config: dict[str, Any]
    ) -> tuple[dict[str, str], str | None]:
        """Validate the user input."""
        errors: dict[str, str] = {}
        token_subject = None
        rheklo = AioKem(session=async_get_clientsession(self.hass))
        try:
            await rheklo.authenticate(config[CONF_EMAIL], config[CONF_PASSWORD])
        except CONNECTION_EXCEPTIONS:
            errors["base"] = "cannot_connect"
        except AuthenticationError:
            errors[CONF_PASSWORD] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            token_subject = rheklo.get_token_subject()
        return errors, token_subject

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth input."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        existing_data = reauth_entry.data
        description_placeholders: dict[str, str] = {
            CONF_EMAIL: existing_data[CONF_EMAIL]
        }
        if user_input is not None:
            errors, _ = await self._async_validate_or_error(
                {**existing_data, **user_input}
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            description_placeholders=description_placeholders,
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
