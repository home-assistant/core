"""Config flow for Microsoft Speech integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_NAME, CONF_REGION
from homeassistant.helpers.selector import (
    LanguageSelector,
    LanguageSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import DOMAIN, SUPPORTED_LANGUAGES, SUPPORTED_REGIONS
from .helper import CannotConnect, InvalidAuth, TooManyRequests, validate_input

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_REGION): SelectSelector(
            SelectSelectorConfig(options=SUPPORTED_REGIONS)
        ),
        vol.Required(CONF_LANGUAGE, default="en-US"): LanguageSelector(
            LanguageSelectorConfig(languages=SUPPORTED_LANGUAGES)
        ),
    }
)


class MicrosoftSpeechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Microsoft Speech."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.entry: ConfigEntry

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except TooManyRequests:
                errors["base"] = "too_many_requests"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        self.entry = self._get_reconfigure_entry()
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except TooManyRequests:
                errors["base"] = "too_many_requests"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry, title=user_input[CONF_NAME], data=user_input
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=self.entry.title): str,
                    vol.Required(
                        CONF_API_KEY, default=self.entry.data[CONF_API_KEY]
                    ): str,
                    vol.Required(
                        CONF_REGION, default=self.entry.data[CONF_REGION]
                    ): SelectSelector(SelectSelectorConfig(options=SUPPORTED_REGIONS)),
                    vol.Required(
                        CONF_LANGUAGE,
                        default=self.entry.data.get(CONF_LANGUAGE, "en-US"),
                    ): LanguageSelector(
                        LanguageSelectorConfig(languages=SUPPORTED_LANGUAGES)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization of an existing entry."""
        self.entry = self._get_reauth_entry()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization of an existing entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Merge existing entry data with new user_input
            new_data = self.entry.data.copy()
            new_data.update(user_input)
            try:
                await validate_input(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except TooManyRequests:
                errors["base"] = "too_many_requests"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry, title=self.entry.title, data=new_data
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )
