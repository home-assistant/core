"""Config flow for the Diyanet integration."""

from __future__ import annotations

import logging
from typing import Any

from pydiyanet import DiyanetApiClient, DiyanetAuthError, DiyanetConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATION_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> DiyanetApiClient:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    client = DiyanetApiClient(session, data[CONF_EMAIL], data[CONF_PASSWORD])

    # Test authentication
    await client.authenticate()

    # Return info and authenticated client for subsequent steps
    return client


class DiyanetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Diyanet."""

    VERSION = 1
    MINOR_VERSION = 1

    _client: DiyanetApiClient
    _email: str | None = None
    _password: str | None = None
    _country_id: int | None = None
    _country_name: str | None = None
    _country_labels: dict[int, str]
    _state_id: int | None = None
    _state_name: str | None = None
    _state_labels: dict[int, str]
    _city_name: str | None = None
    _city_labels: dict[int, str]

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect credentials and authenticate."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                # Validate credentials by authenticating
                self._client = await validate_input(self.hass, user_input)
                email = user_input[CONF_EMAIL]
                self._email = email
                self._password = user_input[CONF_PASSWORD]

                # Prevent duplicate entries for the same email
                await self.async_set_unique_id(email.lower())
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

        data_schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA, user_input or {}
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_select_country(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a country to narrow down states."""
        client = self._client
        errors: dict[str, str] = {}

        if user_input is not None:
            self._country_id = int(user_input["country_id"])
            # Reuse labels from the previously rendered selector options.
            self._country_name = getattr(self, "_country_labels", {}).get(
                self._country_id
            )
            return await self.async_step_select_state()

        try:
            countries = await client.get_countries()
        except DiyanetConnectionError:
            return self.async_abort(reason="cannot_connect")

        options: list[selector.SelectOptionDict] = []
        self._country_labels = {}
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
            if (country_id_raw := item.get("id")) is None:
                continue
            country_id = int(country_id_raw)
            self._country_labels[country_id] = label
            value = str(country_id)
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
        if self._country_id is None:
            raise AbortFlow("missing_context")
        client = self._client
        country_id = self._country_id
        errors: dict[str, str] = {}

        if user_input is not None:
            self._state_id = int(user_input["state_id"])
            # Reuse labels from the previously rendered selector options.
            self._state_name = getattr(self, "_state_labels", {}).get(self._state_id)
            return await self.async_step_select_city()

        try:
            states = await client.get_states(country_id)
        except DiyanetConnectionError:
            return self.async_abort(reason="cannot_connect")

        options: list[selector.SelectOptionDict] = []
        self._state_labels = {}
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
            if (state_id_raw := item.get("id")) is None:
                continue
            state_id = int(state_id_raw)
            self._state_labels[state_id] = label
            value = str(state_id)
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
        if self._state_id is None or self._email is None or self._password is None:
            raise AbortFlow("missing_context")
        client = self._client
        state_id = self._state_id
        email = self._email
        password = self._password
        errors: dict[str, str] = {}

        if user_input is not None:
            city_id = int(user_input["city_id"])
            # Reuse labels from the previously rendered selector options.
            self._city_name = getattr(self, "_city_labels", {}).get(city_id)

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
            return self.async_abort(reason="cannot_connect")

        options: list[selector.SelectOptionDict] = []
        self._city_labels = {}
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
            if (city_id_raw := item.get("id")) is None:
                continue
            city_id = int(city_id_raw)
            self._city_labels[city_id] = label
            value = str(city_id)
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
