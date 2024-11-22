"""Config flow for Google Maps Travel Time integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_MODE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (
    ALL_LANGUAGES,
    ARRIVAL_TIME,
    AVOID_OPTIONS,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DEFAULT_NAME,
    DEPARTURE_TIME,
    DOMAIN,
    TIME_TYPES,
    TRAFFIC_MODELS,
    TRANSIT_PREFS,
    TRANSPORT_TYPES,
    TRAVEL_MODES,
    UNITS,
    UNITS_IMPERIAL,
    UNITS_METRIC,
)
from .helpers import InvalidApiKeyException, UnknownException, validate_config_entry

RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DESTINATION): cv.string,
        vol.Required(CONF_ORIGIN): cv.string,
    }
)

CONFIG_SCHEMA = RECONFIGURE_SCHEMA.extend(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MODE): SelectSelector(
            SelectSelectorConfig(
                options=TRAVEL_MODES,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_MODE,
            )
        ),
        vol.Optional(CONF_LANGUAGE): SelectSelector(
            SelectSelectorConfig(
                options=sorted(ALL_LANGUAGES),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_LANGUAGE,
            )
        ),
        vol.Optional(CONF_AVOID): SelectSelector(
            SelectSelectorConfig(
                options=AVOID_OPTIONS,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_AVOID,
            )
        ),
        vol.Required(CONF_UNITS): SelectSelector(
            SelectSelectorConfig(
                options=UNITS,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_UNITS,
            )
        ),
        vol.Required(CONF_TIME_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=TIME_TYPES,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_TIME_TYPE,
            )
        ),
        vol.Optional(CONF_TIME, default=""): cv.string,
        vol.Optional(CONF_TRAFFIC_MODEL): SelectSelector(
            SelectSelectorConfig(
                options=TRAFFIC_MODELS,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_TRAFFIC_MODEL,
            )
        ),
        vol.Optional(CONF_TRANSIT_MODE): SelectSelector(
            SelectSelectorConfig(
                options=TRANSPORT_TYPES,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_TRANSIT_MODE,
            )
        ),
        vol.Optional(CONF_TRANSIT_ROUTING_PREFERENCE): SelectSelector(
            SelectSelectorConfig(
                options=TRANSIT_PREFS,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_TRANSIT_ROUTING_PREFERENCE,
            )
        ),
    }
)


def default_options(hass: HomeAssistant) -> dict[str, str]:
    """Get the default options."""
    return {
        CONF_MODE: "driving",
        CONF_UNITS: (
            UNITS_IMPERIAL if hass.config.units is US_CUSTOMARY_SYSTEM else UNITS_METRIC
        ),
    }


class GoogleOptionsFlow(OptionsFlow):
    """Handle an options flow for Google Travel Time."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            time_type = user_input.pop(CONF_TIME_TYPE)
            if time := user_input.pop(CONF_TIME, None):
                if time_type == ARRIVAL_TIME:
                    user_input[CONF_ARRIVAL_TIME] = time
                else:
                    user_input[CONF_DEPARTURE_TIME] = time
            return self.async_create_entry(
                title="",
                data=user_input,
            )

        options = self.config_entry.options.copy()
        if CONF_ARRIVAL_TIME in self.config_entry.options:
            options[CONF_TIME_TYPE] = ARRIVAL_TIME
            options[CONF_TIME] = self.config_entry.options[CONF_ARRIVAL_TIME]
        else:
            options[CONF_TIME_TYPE] = DEPARTURE_TIME
            options[CONF_TIME] = self.config_entry.options.get(CONF_DEPARTURE_TIME, "")

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, options),
        )


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str] | None:
    """Validate the user input allows us to connect."""
    try:
        await hass.async_add_executor_job(
            validate_config_entry,
            hass,
            user_input[CONF_API_KEY],
            user_input[CONF_ORIGIN],
            user_input[CONF_DESTINATION],
        )
    except InvalidApiKeyException:
        return {"base": "invalid_auth"}
    except TimeoutError:
        return {"base": "timeout_connect"}
    except UnknownException:
        return {"base": "cannot_connect"}

    return None


class GoogleTravelTimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Maps Travel Time."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GoogleOptionsFlow:
        """Get the options flow for this handler."""
        return GoogleOptionsFlow()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        user_input = user_input or {}
        if user_input:
            errors = await validate_input(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, DEFAULT_NAME),
                    data=user_input,
                    options=default_options(self.hass),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] | None = None
        if user_input is not None:
            errors = await validate_input(self.hass, user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data=user_input
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, self._get_reconfigure_entry().data
            ),
            errors=errors,
        )
