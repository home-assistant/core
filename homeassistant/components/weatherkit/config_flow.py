"""Adds config flow for WeatherKit."""

from collections.abc import Mapping
from typing import Any, override

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

from . import async_migrate_entry
from .const import (
    CONF_KEY_ID,
    CONF_KEY_PEM,
    CONF_SERVICE_ID,
    CONF_TEAM_ID,
    DOMAIN,
    LOGGER,
)


def _build_data_schema(*, key_pem_required: bool) -> vol.Schema:
    """Build the config flow data schema.

    The private key is optional during reconfigure so the user can leave it
    blank to keep the currently configured key.
    """
    key_pem_marker = (
        vol.Required(CONF_KEY_PEM)
        if key_pem_required
        else vol.Optional(CONF_KEY_PEM, default="")
    )
    return vol.Schema(
        {
            vol.Required(CONF_LOCATION): LocationSelector(
                LocationSelectorConfig(radius=False, icon="")
            ),
            # Auth
            vol.Required(CONF_KEY_ID): str,
            vol.Required(CONF_SERVICE_ID): str,
            vol.Required(CONF_TEAM_ID): str,
            key_pem_marker: TextSelector(
                TextSelectorConfig(
                    multiline=True,
                )
            ),
        }
    )


DATA_SCHEMA = _build_data_schema(key_pem_required=True)
RECONFIGURE_DATA_SCHEMA = _build_data_schema(key_pem_required=False)


class WeatherKitUnsupportedLocationError(Exception):
    """Error to indicate a location is unsupported."""


class WeatherKitFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for WeatherKit."""

    VERSION = 2

    @override
    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            error = await self._validate_input(user_input)
            if error:
                errors["base"] = error
            else:
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

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of an existing entry."""
        errors = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            if not user_input[CONF_KEY_PEM]:
                user_input[CONF_KEY_PEM] = reconfigure_entry.data[CONF_KEY_PEM]

            error = await self._validate_input(user_input)
            if error:
                errors["base"] = error
            else:
                # A disabled or not-yet-set-up entry may still be on the old
                # lat/lon-based unique id scheme, since migration only runs
                # during setup. Migrate it now, before its location changes,
                # so the migration can still find the old registry records.
                await async_migrate_entry(self.hass, reconfigure_entry)

                location = user_input.pop(CONF_LOCATION)
                user_input[CONF_LATITUDE] = location[CONF_LATITUDE]
                user_input[CONF_LONGITUDE] = location[CONF_LONGITUDE]

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=f"{user_input[CONF_LATITUDE]}, {user_input[CONF_LONGITUDE]}",
                    data=user_input,
                )

        suggested_values = {
            CONF_KEY_ID: reconfigure_entry.data[CONF_KEY_ID],
            CONF_SERVICE_ID: reconfigure_entry.data[CONF_SERVICE_ID],
            CONF_TEAM_ID: reconfigure_entry.data[CONF_TEAM_ID],
            CONF_LOCATION: {
                CONF_LATITUDE: reconfigure_entry.data[CONF_LATITUDE],
                CONF_LONGITUDE: reconfigure_entry.data[CONF_LONGITUDE],
            },
        }
        data_schema = self.add_suggested_values_to_schema(
            RECONFIGURE_DATA_SCHEMA, suggested_values
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )

    async def _validate_input(self, user_input: dict[str, Any]) -> str | None:
        """Fix up and validate user input, returning an error key on failure."""
        try:
            user_input[CONF_KEY_PEM] = self._fix_key_input(user_input[CONF_KEY_PEM])
            await self._test_config(user_input)
        except WeatherKitUnsupportedLocationError as exception:
            LOGGER.error(exception)
            return "unsupported_location"
        except WeatherKitApiClientAuthenticationError as exception:
            LOGGER.warning(exception)
            return "invalid_auth"
        except WeatherKitApiClientCommunicationError as exception:
            LOGGER.error(exception)
            return "cannot_connect"
        except WeatherKitApiClientError as exception:
            LOGGER.exception(exception)
            return "unknown"
        return None

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
