"""Config flow for Fluss+ integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
)

from .const import CONF_ICON_TYPE, DEFAULT_ICON_TYPE, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): cv.string})

ICON_OPTIONS = [
    SelectOptionDict(value="gate", label="Gate"),
    SelectOptionDict(value="garage", label="Garage"),
    SelectOptionDict(value="door", label="Door"),
    SelectOptionDict(value="boom_gate", label="Boom gate"),
    SelectOptionDict(value="barrier", label="Barrier"),
]


class FlussConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fluss+."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: Any,
    ) -> FlussOptionsFlow:
        """Get the options flow for this handler."""
        return FlussOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            self._async_abort_entries_match({CONF_API_KEY: api_key})
            client = FlussApiClient(
                user_input[CONF_API_KEY], session=async_get_clientsession(self.hass)
            )
            try:
                await client.async_get_devices()
            except FlussApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except FlussApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception occurred")
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(
                    title="My Fluss+ Devices", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth when the API key becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth with a new API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = FlussApiClient(
                user_input[CONF_API_KEY],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.async_get_devices()
            except FlussApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except FlussApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class FlussOptionsFlow(OptionsFlow):
    """Handle Fluss+ options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(
                            CONF_ICON_TYPE, default=DEFAULT_ICON_TYPE
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=ICON_OPTIONS,
                                translation_key="icon_type",
                            )
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
