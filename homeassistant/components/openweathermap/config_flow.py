"""Config flow for OpenWeatherMap."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CONFIG_FLOW_VERSION,
    DEFAULT_LANGUAGE,
    DEFAULT_NAME,
    DEFAULT_OWM_MODE,
    DOMAIN,
    LANGUAGES,
    OWM_MODES,
)
from .utils import build_data_and_options, validate_api_key

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_MODE, default=DEFAULT_OWM_MODE): vol.In(OWM_MODES),
        vol.Optional(CONF_LANGUAGE): vol.In(LANGUAGES),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MODE): vol.In(OWM_MODES),
        vol.Optional(CONF_LANGUAGE): vol.In(LANGUAGES),
    }
)


class OpenWeatherMapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for OpenWeatherMap."""

    VERSION = CONFIG_FLOW_VERSION

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OpenWeatherMapOptionsFlow:
        """Get the options flow for this handler."""
        return OpenWeatherMapOptionsFlow()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        description_placeholders = {}
        ha_data = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
            CONF_LANGUAGE: self.hass.config.language,
        }

        schema_data = {
            **ha_data,
            **user_input,
        }

        if user_input is not None:
            latitude = schema_data[CONF_LATITUDE]
            longitude = schema_data[CONF_LONGITUDE]
            mode = schema_data[CONF_MODE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()

            errors, description_placeholders = await validate_api_key(
                schema_data[CONF_API_KEY], mode
            )

            if not errors:
                data, options = build_data_and_options(schema_data)
                return self.async_create_entry(
                    title=schema_data[CONF_NAME], data=data, options=options
                )

        description_placeholders["doc_url"] = (
            "https://www.home-assistant.io/integrations/openweathermap/"
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, schema_data),
            errors=errors,
            description_placeholders=description_placeholders,
        )


class OpenWeatherMapOptionsFlow(OptionsFlow):
    """Handle options."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    CONF_MODE: self.config_entry.options.get(
                        CONF_MODE,
                        self.config_entry.data.get(CONF_MODE, DEFAULT_OWM_MODE),
                    ),
                    CONF_LANGUAGE: self.config_entry.options.get(
                        CONF_LANGUAGE,
                        self.config_entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                    ),
                },
            ),
        )
