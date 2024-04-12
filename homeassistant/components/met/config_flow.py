"""Config flow to configure Met component."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import (
    CONF_TRACK_HOME,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
    HOME_LOCATION_NAME,
)


@callback
def configured_instances(hass: HomeAssistant) -> set[str]:
    """Return a set of configured met.no instances."""
    entries = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("track_home"):
            entries.append("home")
            continue
        entries.append(
            f"{entry.data.get(CONF_LATITUDE)}-{entry.data.get(CONF_LONGITUDE)}"
        )
    return set(entries)


def _get_data_schema(
    hass: HomeAssistant, config_entry: ConfigEntry | None = None
) -> vol.Schema:
    """Get a schema with default values."""
    # If tracking home or no config entry is passed in, default value come from Home location
    if config_entry is None or config_entry.data.get(CONF_TRACK_HOME, False):
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=HOME_LOCATION_NAME): str,
                vol.Required(CONF_LATITUDE, default=hass.config.latitude): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=hass.config.longitude
                ): cv.longitude,
                vol.Required(
                    CONF_ELEVATION, default=hass.config.elevation
                ): NumberSelector(
                    NumberSelectorConfig(
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=UnitOfLength.METERS,
                    )
                ),
            }
        )
    # Not tracking home, default values come from config entry
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=config_entry.data.get(CONF_NAME)): str,
            vol.Required(
                CONF_LATITUDE, default=config_entry.data.get(CONF_LATITUDE)
            ): cv.latitude,
            vol.Required(
                CONF_LONGITUDE, default=config_entry.data.get(CONF_LONGITUDE)
            ): cv.longitude,
            vol.Required(
                CONF_ELEVATION, default=config_entry.data.get(CONF_ELEVATION)
            ): NumberSelector(
                NumberSelectorConfig(
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfLength.METERS,
                )
            ),
        }
    )


class MetConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Met component."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            if (
                f"{user_input.get(CONF_LATITUDE)}-{user_input.get(CONF_LONGITUDE)}"
                not in configured_instances(self.hass)
            ):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            errors[CONF_NAME] = "already_configured"

        return self.async_show_form(
            step_id="user",
            data_schema=_get_data_schema(self.hass),
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
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow for Met."""
        return MetOptionsFlowHandler(config_entry)


class MetOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Options flow for Met component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure options for Met."""

        if user_input is not None:
            # Update config entry with data from user input
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=user_input
            )
            return self.async_create_entry(
                title=self._config_entry.title, data=user_input
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_get_data_schema(self.hass, config_entry=self._config_entry),
        )
