"""Adds config flow for WeatherKit."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apple_weatherkit.client import (
    WeatherKitApiClient,
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientCommunicationError,
    WeatherKitApiClientError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_KEY_ID,
    CONF_KEY_PEM,
    CONF_SERVICE_ID,
    CONF_TEAM_ID,
    DOMAIN,
    LOGGER,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCATION): LocationSelector(
            LocationSelectorConfig(radius=False, icon="")
        ),
        # Auth
        vol.Required(CONF_KEY_ID): str,
        vol.Required(CONF_SERVICE_ID): str,
        vol.Required(CONF_TEAM_ID): str,
        vol.Required(CONF_KEY_PEM): TextSelector(
            TextSelectorConfig(
                multiline=True,
            )
        ),
    }
)


class WeatherKitUnsupportedLocationError(Exception):
    """Error to indicate a location is unsupported."""


class WeatherKitFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for WeatherKit."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                user_input[CONF_KEY_PEM] = self._fix_key_input(user_input[CONF_KEY_PEM])
                await self._test_config(user_input)
            except WeatherKitUnsupportedLocationError as exception:
                LOGGER.error(exception)
                errors["base"] = "unsupported_location"
            except WeatherKitApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "invalid_auth"
            except WeatherKitApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "cannot_connect"
            except WeatherKitApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                # Flatten location
                location = user_input.pop(CONF_LOCATION)
                user_input[CONF_LATITUDE] = location[CONF_LATITUDE]
                user_input[CONF_LONGITUDE] = location[CONF_LONGITUDE]

                return self.async_create_entry(
                    title=f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}",
                    data=user_input,
                )

        suggested_values: Mapping[str, Any] = {
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            }
        }

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, suggested_values)
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    def _fix_key_input(self, key_input: str) -> str:
        """Fix common user errors with the key input."""
        # OSes may sometimes turn two hyphens (--) into an em dash (—)
        key_input = key_input.replace("—", "--")

        # Trim whitespace and line breaks
        key_input = key_input.strip()

        # Make sure header and footer are present
        header = "-----BEGIN PRIVATE KEY-----"
        if not key_input.startswith(header):
            key_input = f"{header}\n{key_input}"

        footer = "-----END PRIVATE KEY-----"
        if not key_input.endswith(footer):
            key_input += f"\n{footer}"

        return key_input

    async def _test_config(self, user_input: dict[str, Any]) -> None:
        """Validate credentials."""
        client = WeatherKitApiClient(
            key_id=user_input[CONF_KEY_ID],
            service_id=user_input[CONF_SERVICE_ID],
            team_id=user_input[CONF_TEAM_ID],
            key_pem=user_input[CONF_KEY_PEM],
            session=async_get_clientsession(self.hass),
        )

        location = user_input[CONF_LOCATION]
        availability = await client.get_availability(
            location[CONF_LATITUDE],
            location[CONF_LONGITUDE],
        )

        if not availability:
            raise WeatherKitUnsupportedLocationError(
                "API does not support this location"
            )
