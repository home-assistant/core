"""Config flow for the dwd_weather_warnings integration."""

from __future__ import annotations

from typing import Any

from dwdwfsapi import DwdWeatherWarningsAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_REGION_DEVICE_TRACKER, CONF_REGION_IDENTIFIER, DOMAIN
from .util import get_position_data


class DwdWeatherWarningsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the dwd_weather_warnings integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict = {}

        if user_input is not None:
            valid_options = (CONF_REGION_IDENTIFIER, CONF_REGION_DEVICE_TRACKER)

            # Check, if either CONF_REGION_IDENTIFIER or CONF_GPS_TRACKER has been set.
            if all(k not in user_input for k in valid_options):
                errors["base"] = "no_identifier"
            elif all(k in user_input for k in valid_options):
                errors["base"] = "ambiguous_identifier"
            elif CONF_REGION_IDENTIFIER in user_input:
                # Validate region identifier using the API
                identifier = user_input[CONF_REGION_IDENTIFIER]

                if not await self.hass.async_add_executor_job(
                    DwdWeatherWarningsAPI, identifier
                ):
                    errors["base"] = "invalid_identifier"

                if not errors:
                    # Set the unique ID for this config entry.
                    await self.async_set_unique_id(identifier)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=identifier, data=user_input)
            elif CONF_REGION_DEVICE_TRACKER in user_input:
                # Validate position using the API
                device_tracker = user_input[CONF_REGION_DEVICE_TRACKER]
                position = get_position_data(self.hass, device_tracker)

                if not await self.hass.async_add_executor_job(
                    DwdWeatherWarningsAPI, position
                ):
                    errors["base"] = "invalid_identifier"

                # Position is valid here, because the API call was successful.
                if not errors and position is not None:
                    # Set the unique ID for this config entry.
                    await self.async_set_unique_id(f"{position[0]}-{position[1]}")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=device_tracker.removeprefix("device_tracker."),
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_REGION_IDENTIFIER): cv.string,
                    vol.Optional(CONF_REGION_DEVICE_TRACKER): EntitySelector(
                        EntitySelectorConfig(domain="device_tracker")
                    ),
                }
            ),
        )
