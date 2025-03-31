"""Config flow for the dwd_weather_warnings integration."""

from __future__ import annotations

from typing import Any

from dwdwfsapi import DwdWeatherWarningsAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import CONF_REGION_DEVICE_TRACKER, CONF_REGION_IDENTIFIER, DOMAIN
from .exceptions import EntityNotFoundError
from .util import get_position_data

EXCLUSIVE_OPTIONS = (CONF_REGION_IDENTIFIER, CONF_REGION_DEVICE_TRACKER)


class DwdWeatherWarningsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for the dwd_weather_warnings integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict = {}

        if user_input is not None:
            # Check, if either CONF_REGION_IDENTIFIER or CONF_GPS_TRACKER has been set.
            if all(k not in user_input for k in EXCLUSIVE_OPTIONS):
                errors["base"] = "no_identifier"
            elif all(k in user_input for k in EXCLUSIVE_OPTIONS):
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
            else:  # CONF_REGION_DEVICE_TRACKER
                device_tracker = user_input[CONF_REGION_DEVICE_TRACKER]
                registry = er.async_get(self.hass)
                entity_entry = registry.async_get(device_tracker)

                if entity_entry is None:
                    errors["base"] = "entity_not_found"
                else:
                    try:
                        position = get_position_data(self.hass, entity_entry.id)
                    except EntityNotFoundError:
                        errors["base"] = "entity_not_found"
                    except AttributeError:
                        errors["base"] = "attribute_not_found"
                    else:
                        # Validate position using the API
                        if not await self.hass.async_add_executor_job(
                            DwdWeatherWarningsAPI, position
                        ):
                            errors["base"] = "invalid_identifier"

                # Position is valid here, because the API call was successful.
                if not errors and position is not None and entity_entry is not None:
                    # Set the unique ID for this config entry.
                    await self.async_set_unique_id(entity_entry.id)
                    self._abort_if_unique_id_configured()

                    # Replace entity ID with registry ID for more stability.
                    user_input[CONF_REGION_DEVICE_TRACKER] = entity_entry.id

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
