"""PurpleAir config flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_SHOW_ON_MAP
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .config_validation import ConfigValidation
from .const import DOMAIN, SCHEMA_VERSION
from .options_flow import PurpleAirOptionsFlow
from .subentry_flow import PurpleAirSubentryFlow

TITLE: Final[str] = "PurpleAir"

CONF_REAUTH_CONFIRM: Final[str] = "reauth_confirm"
CONF_REAUTH_SUCCESSFUL: Final[str] = "reauth_successful"
CONF_RECONFIGURE_SUCCESSFUL: Final[str] = "reconfigure_successful"
CONF_RECONFIGURE: Final[str] = "reconfigure"
CONF_SENSOR: Final[str] = "sensor"


class PurpleAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow."""

    VERSION = SCHEMA_VERSION

    def __init__(self) -> None:
        """Initialize."""
        self._flow_data: dict[str, Any] = {}

    async def _async_get_title(self) -> str:
        """Get instance title."""
        title: str = TITLE
        config_list = self.hass.config_entries.async_loaded_entries(DOMAIN)
        if len(config_list) > 0:
            title = f"{TITLE} ({len(config_list)})"
        return title

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Get config subentries."""
        return {
            CONF_SENSOR: PurpleAirSubentryFlow,
        }

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PurpleAirOptionsFlow:
        """Get options flow."""
        return PurpleAirOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initialization flow."""
        return await self.async_step_api_key(user_input)

    @property
    def api_key_schema(self) -> vol.Schema:
        """API key entry schema."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_API_KEY, default=self._flow_data.get(CONF_API_KEY)
                ): cv.string,
            }
        )

    async def async_step_api_key(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle API key flow."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_API_KEY, data_schema=self.api_key_schema
            )

        self._flow_data[CONF_API_KEY] = str(user_input.get(CONF_API_KEY))
        validation = await ConfigValidation.async_validate_api_key(
            self.hass, self._flow_data[CONF_API_KEY]
        )
        if validation.errors:
            return self.async_show_form(
                step_id=CONF_API_KEY,
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        await self.async_set_unique_id(self._flow_data[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=await self._async_get_title(),
            data={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            options={CONF_SHOW_ON_MAP: False},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    # Keep logic in sync with async_step_api_key()
    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth step."""
        if user_input is None:
            return self.async_show_form(
                step_id=CONF_REAUTH_CONFIRM,
                data_schema=self.api_key_schema,
            )

        self._flow_data[CONF_API_KEY] = str(user_input[CONF_API_KEY])
        validation = await ConfigValidation.async_validate_api_key(
            self.hass, self._flow_data[CONF_API_KEY]
        )
        if validation.errors:
            return self.async_show_form(
                step_id=CONF_REAUTH_CONFIRM,
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        await self.async_set_unique_id(self._flow_data[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data_updates={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            reason=CONF_REAUTH_SUCCESSFUL,
        )

    # Keep logic in sync with async_step_api_key()
    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        if user_input is None:
            self._flow_data[CONF_API_KEY] = self._get_reconfigure_entry().data.get(
                CONF_API_KEY
            )
            return self.async_show_form(
                step_id=CONF_RECONFIGURE,
                data_schema=self.api_key_schema,
            )

        self._flow_data[CONF_API_KEY] = str(user_input[CONF_API_KEY])
        validation = await ConfigValidation.async_validate_api_key(
            self.hass, self._flow_data[CONF_API_KEY]
        )
        if validation.errors:
            return self.async_show_form(
                step_id=CONF_RECONFIGURE,
                data_schema=self.api_key_schema,
                errors=validation.errors,
            )

        await self.async_set_unique_id(self._flow_data[CONF_API_KEY])
        self._abort_if_unique_id_configured()

        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(),
            data_updates={CONF_API_KEY: self._flow_data[CONF_API_KEY]},
            reason=CONF_RECONFIGURE_SUCCESSFUL,
        )
