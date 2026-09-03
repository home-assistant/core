"""Config flow for the Foreca integration."""

import logging
from typing import Any, override

from pyforeca import ForecaApiClient, ForecaAuthError, ForecaError, format_location
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ForecaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Foreca."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            latitude = user_input[CONF_LOCATION][CONF_LATITUDE]
            longitude = user_input[CONF_LOCATION][CONF_LONGITUDE]
            client = ForecaApiClient(
                user_input[CONF_API_KEY],
                session=async_get_clientsession(self.hass),
            )
            location = format_location(lon=longitude, lat=latitude)
            try:
                info = await client.location_info(location)
                await client.current(location)
            except ForecaAuthError:
                errors["base"] = "invalid_auth"
            except ForecaError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error validating Foreca API key")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(f"{latitude:.4f}-{longitude:.4f}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.name or "Foreca",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LATITUDE: latitude,
                        CONF_LONGITUDE: longitude,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(
                        CONF_LOCATION,
                        default={
                            CONF_LATITUDE: self.hass.config.latitude,
                            CONF_LONGITUDE: self.hass.config.longitude,
                        },
                    ): LocationSelector(),
                }
            ),
            errors=errors,
        )
