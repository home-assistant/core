"""Config flow for AirNow integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from pyairnow.api import WebServiceAPI
from pyairnow.errors import AirNowError, EmptyResponseError, InvalidKeyError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# Documentation URL for API key generation
_API_KEY_URL = "https://docs.airnowapi.org/account/request/"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = WebServiceAPI(data[CONF_API_KEY], session=session)

    lat = data[CONF_LATITUDE]
    lng = data[CONF_LONGITUDE]

    # Check that the provided latitude/longitude provide a response
    try:
        test_data = await client.observations.latLong(lat, lng)

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

    VERSION = 3

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Set a unique id based on latitude/longitude
            location: dict[str, Any] = user_input[CONF_LOCATION]
            await self.async_set_unique_id(
                f"{location[CONF_LATITUDE]}-{location[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            if not (
                errors := await self._async_validate_input({**user_input, **location})
            ):
                # Create Entry
                return self.async_create_entry(
                    title=(
                        f"AirNow Sensor at {location[CONF_LATITUDE]},"
                        f" {location[CONF_LONGITUDE]}"
                    ),
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_LATITUDE: location[CONF_LATITUDE],
                        CONF_LONGITUDE: location[CONF_LONGITUDE],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                        probatio.Required(CONF_LOCATION): LocationSelector(
                            LocationSelectorConfig(radius=False)
                        ),
                    }
                ),
                user_input
                or {
                    CONF_LOCATION: {
                        CONF_LATITUDE: self.hass.config.latitude,
                        CONF_LONGITUDE: self.hass.config.longitude,
                    }
                },
            ),
            description_placeholders={"api_key_url": _API_KEY_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None and not (
            errors := await self._async_validate_input(
                {**reauth_entry.data, **user_input}
            )
        ):
            return self.async_update_reload_and_abort(
                reauth_entry, data_updates=user_input
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            description_placeholders={
                "name": reauth_entry.title,
                "api_key_url": _API_KEY_URL,
            },
            errors=errors,
        )

    async def _async_validate_input(self, data: dict[str, Any]) -> dict[str, str]:
        """Validate the input and return any errors."""
        try:
            await validate_input(self.hass, data)
        except CannotConnect:
            return {"base": "cannot_connect"}
        except InvalidAuth:
            return {"base": "invalid_auth"}
        except InvalidLocation:
            return {"base": "invalid_location"}
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return {"base": "unknown"}
        return {}


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidLocation(HomeAssistantError):
    """Error to indicate the location is invalid."""
