"""Config flow for the Diyanet integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DiyanetApiClient, DiyanetAuthError, DiyanetConnectionError
from .const import CONF_LOCATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Raised when the integration cannot connect during config flow."""


class InvalidAuth(HomeAssistantError):
    """Raised when provided credentials are invalid during config flow."""


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = DiyanetApiClient(session, data[CONF_EMAIL], data[CONF_PASSWORD])

    # Test authentication
    await client.authenticate()

    # Return info that you want to store in the config entry
    return {"title": f"Diyanet ({data[CONF_EMAIL]})"}


class DiyanetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Diyanet."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow runtime state."""
        self._client: DiyanetApiClient | None = None
        self._email: str | None = None
        self._password: str | None = None
        self._country_id: int | None = None
        self._country_name: str | None = None
        self._state_id: int | None = None
        self._state_name: str | None = None
        self._city_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect credentials and authenticate."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                # Validate credentials by authenticating
                await validate_input(self.hass, user_input)
                self._email = user_input[CONF_EMAIL]
                self._password = user_input[CONF_PASSWORD]
                # Create API client for subsequent steps
                session = async_get_clientsession(self.hass)
                self._client = DiyanetApiClient(session, self._email, self._password)
                await self._client.authenticate()

                # Prevent duplicate entries for the same email
                await self.async_set_unique_id(self._email.lower())
                self._abort_if_unique_id_configured()

                # Proceed to country selection
                return await self.async_step_select_country()
            except DiyanetConnectionError:
                errors["base"] = "cannot_connect"
            except DiyanetAuthError:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                # Let Home Assistant handle aborts (e.g., already configured)
                raise
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_select_country(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a country to narrow down states."""
        if self._client is None:
            raise AbortFlow("missing_context")
        client = self._client
        errors: dict[str, str] = {}

        if user_input is not None:
            self._country_id = int(user_input["country_id"])
            # Store country name for display
            try:
                countries = await client.get_countries()
                for country in countries:
                    if country.get("id") == self._country_id:
                        self._country_name = str(
                            country.get("code")
                            or country.get("name")
                            or country.get("Code")
                            or country.get("Name")
                        )
                        break
            except DiyanetConnectionError:
                pass
            return await self.async_step_select_state()

        try:
            countries = await client.get_countries()
        except DiyanetConnectionError:
            errors["base"] = "cannot_connect"
            countries = []

        options: list[selector.SelectOptionDict] = []
        for item in countries:
            # Prefer code for english-friendly labels, fallback to name
            label: str = str(
                item.get("code")
                or item.get("name")
                or item.get("Code")
                or item.get("Name")
                or item.get("title")
                or item.get("Title")
                or item.get("id")
            )
            value = str(item.get("id"))
            options.append(selector.SelectOptionDict(label=label, value=value))

        schema = vol.Schema(
            {
                vol.Required("country_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="select_country", data_schema=schema, errors=errors
        )

    async def async_step_select_state(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a state within the chosen country."""
        if self._client is None or self._country_id is None:
            raise AbortFlow("missing_context")
        client = self._client
        country_id = self._country_id
        errors: dict[str, str] = {}

        if user_input is not None:
            self._state_id = int(user_input["state_id"])
            # Store state name for display
            try:
                states = await client.get_states(country_id)
                for state in states:
                    if state.get("id") == self._state_id:
                        self._state_name = str(
                            state.get("code")
                            or state.get("name")
                            or state.get("Code")
                            or state.get("Name")
                        )
                        break
            except DiyanetConnectionError:
                pass
            return await self.async_step_select_city()

        try:
            states = await client.get_states(country_id)
        except DiyanetConnectionError:
            errors["base"] = "cannot_connect"
            states = []

        options: list[selector.SelectOptionDict] = []
        for item in states:
            label: str = str(
                item.get("code")
                or item.get("name")
                or item.get("Code")
                or item.get("Name")
                or item.get("title")
                or item.get("Title")
                or item.get("id")
            )
            value = str(item.get("id"))
            options.append(selector.SelectOptionDict(label=label, value=value))

        schema = vol.Schema(
            {
                vol.Required("state_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="select_state", data_schema=schema, errors=errors
        )

    async def async_step_select_city(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a city within the chosen state and finish."""
        if (
            self._client is None
            or self._state_id is None
            or self._email is None
            or self._password is None
        ):
            raise AbortFlow("missing_context")
        client = self._client
        state_id = self._state_id
        email = self._email
        password = self._password
        errors: dict[str, str] = {}

        if user_input is not None:
            city_id = int(user_input["city_id"])
            # Store city name for display
            try:
                cities = await client.get_cities(state_id)
                for city in cities:
                    if city.get("id") == city_id:
                        code = (
                            city.get("code")
                            or city.get("Code")
                            or city.get("shortName")
                            or city.get("ShortName")
                        )
                        name = (
                            city.get("name")
                            or city.get("Name")
                            or city.get("title")
                            or city.get("Title")
                        )
                        if code and name and str(code) != str(name):
                            self._city_name = f"{code} – {name}"
                        else:
                            self._city_name = str(code or name)
                        break
            except DiyanetConnectionError:
                pass

            try:
                # Validate city works by fetching prayer times
                await client.get_prayer_times(city_id)
            except DiyanetConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception while validating city")
                errors["base"] = "unknown"
            else:
                # Create the final entry with location in title
                location_parts = tuple(
                    p
                    for p in (self._city_name, self._state_name, self._country_name)
                    if p
                )
                location_str = (
                    ", ".join(location_parts)
                    if location_parts
                    else f"Location {city_id}"
                )
                title = f"Diyanet ({location_str})"
                data = {
                    CONF_EMAIL: email,
                    CONF_PASSWORD: password,
                    CONF_LOCATION_ID: city_id,
                }
                return self.async_create_entry(title=title, data=data)

        try:
            cities = await client.get_cities(state_id)
        except DiyanetConnectionError:
            errors["base"] = "cannot_connect"
            cities = []

        options: list[selector.SelectOptionDict] = []
        for item in cities:
            # Show "CODE – Name" if both available; otherwise whichever exists
            code = (
                item.get("code")
                or item.get("Code")
                or item.get("shortName")
                or item.get("ShortName")
            )
            name = (
                item.get("name")
                or item.get("Name")
                or item.get("title")
                or item.get("Title")
            )
            if code and name and str(code) != str(name):
                label = f"{code} – {name}"
            else:
                label = str(code or name or item.get("id"))
            value = str(item.get("id"))
            options.append(selector.SelectOptionDict(label=label, value=value))

        schema = vol.Schema(
            {
                vol.Required("city_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options, mode=selector.SelectSelectorMode.DROPDOWN
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="select_city", data_schema=schema, errors=errors
        )
