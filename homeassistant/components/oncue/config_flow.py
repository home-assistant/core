"""Config flow for Oncue integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiooncue import LoginFailedException, Oncue
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONNECTION_EXCEPTIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OncueConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oncue."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the oncue config flow."""
        self.reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not (errors := await self._async_validate_or_error(user_input)):
                normalized_username = user_input[CONF_USERNAME].lower()
                await self.async_set_unique_id(normalized_username)
                self._abort_if_unique_id_configured(
                    updates={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
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
            await Oncue(
                config[CONF_USERNAME],
                config[CONF_PASSWORD],
                async_get_clientsession(self.hass),
            ).async_login()
        except CONNECTION_EXCEPTIONS:
            errors["base"] = "cannot_connect"
        except LoginFailedException:
            errors[CONF_PASSWORD] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        return errors

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth."""
        entry_id = self.context["entry_id"]
        self.reauth_entry = self.hass.config_entries.async_get_entry(entry_id)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth input."""
        errors: dict[str, str] = {}
        existing_entry = self.reauth_entry
        assert existing_entry
        existing_data = existing_entry.data
        description_placeholders: dict[str, str] = {
            CONF_USERNAME: existing_data[CONF_USERNAME]
        }
        if user_input is not None:
            new_config = {**existing_data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            if not (errors := await self._async_validate_or_error(new_config)):
                return self.async_update_reload_and_abort(
                    existing_entry, data=new_config
                )

        return self.async_show_form(
            description_placeholders=description_placeholders,
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
