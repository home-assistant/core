"""Config flow for AirNow integration."""

import logging
from typing import Any

from pyairnow import WebServiceAPI
from pyairnow.errors import AirNowError, EmptyResponseError, InvalidKeyError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = WebServiceAPI(data[CONF_API_KEY], session=session)

    lat = data[CONF_LATITUDE]
    lng = data[CONF_LONGITUDE]
    distance = data[CONF_RADIUS]

    # Check that the provided latitude/longitude provide a response
    try:
        test_data = await client.observations.latLong(lat, lng, distance=distance)

    except InvalidKeyError as exc:
        raise InvalidAuth from exc
    except AirNowError as exc:
        raise CannotConnect from exc
    except EmptyResponseError as exc:
        raise InvalidLocation from exc

    if not test_data:
        raise InvalidLocation

    # Validation Succeeded
    return True


class AirNowConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirNow."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            # Set a unique id based on latitude/longitude
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}-{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            try:
                # Validate inputs
                await validate_input(self.hass, user_input)

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidLocation:
                errors["base"] = "invalid_location"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create Entry
                radius = user_input.pop(CONF_RADIUS)
                return self.async_create_entry(
                    title=(
                        f"AirNow Sensor at {user_input[CONF_LATITUDE]},"
                        f" {user_input[CONF_LONGITUDE]}"
                    ),
                    data=user_input,
                    options={CONF_RADIUS: radius},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(
                        CONF_LATITUDE, default=self.hass.config.latitude
                    ): cv.latitude,
                    vol.Optional(
                        CONF_LONGITUDE, default=self.hass.config.longitude
                    ): cv.longitude,
                    vol.Optional(CONF_RADIUS, default=150): vol.All(
                        int, vol.Range(min=5)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        return AirNowOptionsFlowHandler(config_entry)


class AirNowOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle an options flow for AirNow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_RADIUS): vol.All(
                    int,
                    vol.Range(min=5),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                options_schema, self.config_entry.options
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidLocation(HomeAssistantError):
    """Error to indicate the location is invalid."""
