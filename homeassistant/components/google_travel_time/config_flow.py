"""Config flow for Google Maps Travel Time integration."""

from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_MODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TimeSelector,
)
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (
    ARRIVAL_TIME,
    CONF_ARRIVAL_TIME,
    CONF_AVOID,
    CONF_DEPARTURE_TIME,
    CONF_DESTINATION,
    CONF_ORIGIN,
    CONF_REFERRER,
    CONF_TIME,
    CONF_TIME_TYPE,
    CONF_TRAFFIC_MODEL,
    CONF_TRANSIT_MODE,
    CONF_TRANSIT_ROUTING_PREFERENCE,
    CONF_UNITS,
    DEFAULT_NAME,
    DEPARTURE_TIME,
    DOMAIN,
    SECTION_API_KEY_OPTIONS,
    TRAVEL_MODES,
    UNITS_IMPERIAL,
    UNITS_METRIC,
)
from .helpers import (
    InvalidApiKeyException,
    InvalidReferrerException,
    PermissionDeniedException,
    UnknownException,
    validate_config_entry,
)
from .schemas import (
    AVOID_SELECTOR,
    LANGUAGE_SELECTOR,
    TIME_TYPE_SELECTOR,
    TRAFFIC_MODEL_SELECTOR,
    TRANSIT_MODE_SELECTOR,
    TRANSIT_ROUTING_PREFERENCE_SELECTOR,
    UNITS_SELECTOR,
)

DESCRIPTION_PLACEHOLDERS = {
    "restricting_api_keys_url": "https://developers.google.com/maps/api-security-best-practices#restricting-api-keys",
}

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
        probatio.Required(CONF_DESTINATION): cv.string,
        probatio.Required(CONF_ORIGIN): cv.string,
        probatio.Optional(SECTION_API_KEY_OPTIONS): section(
            probatio.Schema({probatio.Optional(CONF_REFERRER): cv.string}),
            {"collapsed": True},
        ),
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_LANGUAGE): LANGUAGE_SELECTOR,
        probatio.Optional(CONF_AVOID): AVOID_SELECTOR,
        probatio.Optional(CONF_TRAFFIC_MODEL): TRAFFIC_MODEL_SELECTOR,
        probatio.Optional(CONF_TRANSIT_MODE): TRANSIT_MODE_SELECTOR,
        probatio.Optional(
            CONF_TRANSIT_ROUTING_PREFERENCE
        ): TRANSIT_ROUTING_PREFERENCE_SELECTOR,
        probatio.Required(CONF_MODE): SelectSelector(
            SelectSelectorConfig(
                options=TRAVEL_MODES,
                sort=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_MODE,
            )
        ),
        probatio.Required(CONF_UNITS): UNITS_SELECTOR,
        probatio.Required(CONF_TIME_TYPE): TIME_TYPE_SELECTOR,
        probatio.Optional(CONF_TIME): TimeSelector(),
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


def _extract_entry_data(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten the API key options section into the entry data."""
    data = {
        key: value
        for key, value in user_input.items()
        if key != SECTION_API_KEY_OPTIONS
    }
    if referrer := user_input.get(SECTION_API_KEY_OPTIONS, {}).get(CONF_REFERRER):
        data[CONF_REFERRER] = referrer
    return data


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, str] | None:
    """Validate the user input allows us to connect."""
    try:
        await validate_config_entry(
            hass,
            user_input[CONF_API_KEY],
            user_input[CONF_ORIGIN],
            user_input[CONF_DESTINATION],
            user_input.get(SECTION_API_KEY_OPTIONS, {}).get(CONF_REFERRER),
        )
    except PermissionDeniedException:
        return {"base": "permission_denied"}
    except InvalidApiKeyException:
        return {"base": "invalid_auth"}
    except InvalidReferrerException:
        return {"base": "invalid_referrer"}
    except TimeoutError:
        return {"base": "timeout_connect"}
    except UnknownException:
        return {"base": "cannot_connect"}

    return None


class GoogleTravelTimeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Maps Travel Time."""

    VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GoogleOptionsFlow:
        """Get the options flow for this handler."""
        return GoogleOptionsFlow()

    @override
    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] | None = None
        user_input = user_input or {}
        if user_input:
            errors = await validate_input(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=_extract_entry_data(user_input),
                    options=default_options(self.hass),
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONFIG_SCHEMA, user_input),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
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
                    self._get_reconfigure_entry(), data=_extract_entry_data(user_input)
                )

        entry_data = self._get_reconfigure_entry().data
        suggested_values = {
            key: value for key, value in entry_data.items() if key != CONF_REFERRER
        }
        if referrer := entry_data.get(CONF_REFERRER):
            suggested_values[SECTION_API_KEY_OPTIONS] = {CONF_REFERRER: referrer}
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, suggested_values
            ),
            errors=errors,
            description_placeholders=DESCRIPTION_PLACEHOLDERS,
        )
