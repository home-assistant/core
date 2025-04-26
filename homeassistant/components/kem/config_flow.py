"""Config flow for KEM integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiokem import AuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONNECTION_EXCEPTIONS, DOMAIN
from .data import ConfigFlowAioKem

_LOGGER = logging.getLogger(__name__)


class KemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kem."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (errors := await self._async_validate_or_error(user_input)):
                username: str = user_input[CONF_USERNAME]
                password: str = user_input[CONF_PASSWORD]
                normalized_username = username.lower()
                await self.async_set_unique_id(normalized_username)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    }
                )
                return self.async_create_entry(
                    title=normalized_username, data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def _async_validate_or_error(self, config: dict[str, Any]) -> dict[str, str]:
        """Validate the user input."""
        errors: dict[str, str] = {}
        try:
            kem = ConfigFlowAioKem(
                username=config[CONF_USERNAME],
                password=config[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            await kem.authenticate(config[CONF_USERNAME], config[CONF_PASSWORD])
        except CONNECTION_EXCEPTIONS:
            errors["base"] = "cannot_connect"
        except AuthenticationError:
            errors[CONF_PASSWORD] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors

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
            CONF_USERNAME: existing_data[CONF_USERNAME]
        }
        if user_input is not None:
            new_config = {**existing_data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            if not (errors := await self._async_validate_or_error(new_config)):
                return self.async_update_reload_and_abort(reauth_entry, data=new_config)

        return self.async_show_form(
            description_placeholders=description_placeholders,
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
