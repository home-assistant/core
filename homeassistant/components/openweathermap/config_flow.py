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
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_MODE,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    LanguageSelector,
    LanguageSelectorConfig,
    LocationSelector,
    LocationSelectorConfig,
)

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
        vol.Required(CONF_LOCATION): LocationSelector(
            LocationSelectorConfig(radius=False)
        ),
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): LanguageSelector(
            LanguageSelectorConfig(languages=LANGUAGES, native_name=True)
        ),
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_MODE, default=DEFAULT_OWM_MODE): vol.In(OWM_MODES),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): LanguageSelector(
            LanguageSelectorConfig(languages=LANGUAGES, native_name=True)
        ),
        vol.Optional(CONF_MODE, default=DEFAULT_OWM_MODE): vol.In(OWM_MODES),
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

        if user_input is not None:
            latitude = user_input[CONF_LOCATION][CONF_LATITUDE]
            longitude = user_input[CONF_LOCATION][CONF_LONGITUDE]
            mode = user_input[CONF_MODE]

            await self.async_set_unique_id(f"{latitude}-{longitude}")
            self._abort_if_unique_id_configured()

            errors, description_placeholders = await validate_api_key(
                user_input[CONF_API_KEY], mode
            )

            if not errors:
                # Flatten location
                location = user_input.pop(CONF_LOCATION)
                user_input[CONF_LATITUDE] = location[CONF_LATITUDE]
                user_input[CONF_LONGITUDE] = location[CONF_LONGITUDE]
                data, options = build_data_and_options(user_input)
                return self.async_create_entry(
                    title=DEFAULT_NAME, data=data, options=options
                )
            schema_data = user_input
        else:
            schema_data = {
                CONF_LOCATION: {
                    CONF_LATITUDE: self.hass.config.latitude,
                    CONF_LONGITUDE: self.hass.config.longitude,
                },
                CONF_LANGUAGE: self.hass.config.language,
            }

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
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
