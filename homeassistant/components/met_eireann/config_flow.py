"""Config flow to configure Met Éireann component."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN


class MetEireannFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Met Eireann component."""

    VERSION = 2

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            # Check if an identical entity is already configured
            loc = user_input[CONF_LOCATION]
            await self.async_set_unique_id(
                f"{loc[CONF_LATITUDE]},{loc[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()
        else:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    probatio.Schema(
                        {
                            probatio.Required(CONF_LOCATION): LocationSelector(
                                LocationSelectorConfig(radius=False)
                            ),
                            probatio.Required(CONF_ELEVATION): int,
                        }
                    ),
                    {
                        CONF_LOCATION: {
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                        CONF_ELEVATION: self.hass.config.elevation,
                    },
                ),
            )

        return self.async_create_entry(title="Met Éireann", data=user_input)
