"""Config flow for SMN Weather integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    ARGENTINA_MAX_LATITUDE,
    ARGENTINA_MAX_LONGITUDE,
    ARGENTINA_MIN_LATITUDE,
    ARGENTINA_MIN_LONGITUDE,
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_validate_location(
    hass: HomeAssistant, latitude: float, longitude: float
) -> dict[str, str] | None:
    """Validate the location coordinates."""
    # Basic validation - could be extended to check if location is in Argentina
    if not (-90 <= latitude <= 90):
        return {"base": "invalid_latitude"}
    if not (-180 <= longitude <= 180):
        return {"base": "invalid_longitude"}

    # Optional: Check if coordinates are roughly in Argentina
    if not (ARGENTINA_MIN_LATITUDE <= latitude <= ARGENTINA_MAX_LATITUDE):
        _LOGGER.warning(
            "Latitude %s is outside Argentina bounds (approx. %s to %s)",
            latitude,
            ARGENTINA_MIN_LATITUDE,
            ARGENTINA_MAX_LATITUDE,
        )
    if not (ARGENTINA_MIN_LONGITUDE <= longitude <= ARGENTINA_MAX_LONGITUDE):
        _LOGGER.warning(
            "Longitude %s is outside Argentina bounds (approx. %s to %s)",
            longitude,
            ARGENTINA_MIN_LONGITUDE,
            ARGENTINA_MAX_LONGITUDE,
        )

    return None


class ArgentinaSMNConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SMN Weather."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            latitude = user_input[CONF_LATITUDE]
            longitude = user_input[CONF_LONGITUDE]
            name = user_input[CONF_NAME]

            # Validate coordinates
            validation_errors = await async_validate_location(
                self.hass, latitude, longitude
            )
            if validation_errors:
                errors.update(validation_errors)
            else:
                # Set unique ID
                unique_id = f"{latitude}-{longitude}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Create entry
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_LATITUDE: latitude,
                        CONF_LONGITUDE: longitude,
                    },
                )

        # Show form - pre-fill with home coordinates
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE, default=self.hass.config.latitude
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE, default=self.hass.config.longitude
                ): cv.longitude,
                vol.Required(CONF_NAME): cv.string,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_onboarding(
        self, data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle onboarding step."""
        # Don't create an entry if latitude or longitude isn't set.
        # Also, filters out our onboarding default location.
        if (
            not self.hass.config.latitude
            or not self.hass.config.longitude
            or (
                self.hass.config.latitude == DEFAULT_HOME_LATITUDE
                and self.hass.config.longitude == DEFAULT_HOME_LONGITUDE
            )
        ):
            return self.async_abort(reason="no_home")

        return await self.async_step_user()
