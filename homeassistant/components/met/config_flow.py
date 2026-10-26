"""Config flow to configure Met component."""

from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_TRACK_HOME,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DEFAULT_NAME,
    DOMAIN,
    HOME_LOCATION_NAME,
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_LOCATION): LocationSelector(
            LocationSelectorConfig(radius=False)
        ),
        probatio.Required(CONF_ELEVATION): NumberSelector(
            NumberSelectorConfig(
                mode=NumberSelectorMode.BOX, unit_of_measurement=UnitOfLength.METERS
            )
        ),
    }
)


@callback
def configured_instances(hass: HomeAssistant) -> set[str]:
    """Return a set of configured met.no instances."""
    entries = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("track_home"):
            entries.append("home")
            continue
        location = entry.data.get(CONF_LOCATION, entry.data)
        entries.append(f"{location[CONF_LATITUDE]}-{location[CONF_LONGITUDE]}")
    return set(entries)


def _fixed_location_title(data: Mapping[str, Any]) -> str:
    """Return the generated title for a fixed location."""
    return f"{DEFAULT_NAME} ({data[CONF_LATITUDE]}, {data[CONF_LONGITUDE]})"


def _has_generated_title(config_entry: ConfigEntry) -> bool:
    """Return if the entry title still matches an integration-generated title."""
    if config_entry.data.get(CONF_TRACK_HOME, False):
        return config_entry.title == HOME_LOCATION_NAME

    return config_entry.title == _fixed_location_title(config_entry.data[CONF_LOCATION])


class MetConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Met component."""

    VERSION = 2
    MINOR_VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            location = user_input[CONF_LOCATION]
            if (
                f"{location[CONF_LATITUDE]}-{location[CONF_LONGITUDE]}"
                not in configured_instances(self.hass)
            ):
                return self.async_create_entry(
                    title=_fixed_location_title(location), data=user_input
                )
            errors["base"] = "already_configured"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input
                or {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    },
                    CONF_ELEVATION: self.hass.config.elevation,
                },
            ),
            errors=errors,
        )

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by onboarding."""
        # Don't create entry if latitude or longitude isn't set.
        # Also, filters out our onboarding default location.
        if (not self.hass.config.latitude and not self.hass.config.longitude) or (
            self.hass.config.latitude == DEFAULT_HOME_LATITUDE
            and self.hass.config.longitude == DEFAULT_HOME_LONGITUDE
        ):
            return self.async_abort(reason="no_home")

        return self.async_create_entry(
            title=HOME_LOCATION_NAME, data={CONF_TRACK_HOME: True}
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> MetOptionsFlowHandler:
        """Get the options flow for Met."""
        return MetOptionsFlowHandler()


class MetOptionsFlowHandler(OptionsFlowWithReload):
    """Options flow for Met component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure options for Met."""

        if user_input is not None:
            title = (
                _fixed_location_title(user_input[CONF_LOCATION])
                if _has_generated_title(self.config_entry)
                else self.config_entry.title
            )
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input, title=title
            )
            return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input
                or (
                    self.config_entry.data
                    if not self.config_entry.data.get(CONF_TRACK_HOME, False)
                    else {
                        CONF_LOCATION: {
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                        CONF_ELEVATION: self.hass.config.elevation,
                    }
                ),
            ),
        )
