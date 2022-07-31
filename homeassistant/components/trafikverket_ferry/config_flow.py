"""Adds config flow for Trafikverket Ferry integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pytrafikverket import TrafikverketFerry
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_WEEKDAY, WEEKDAYS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_FROM, CONF_TIME, CONF_TO, DOMAIN
from .util import create_unique_id

ERROR_INVALID_AUTH = "Source: Security, message: Invalid authentication"
ERROR_INVALID_ROUTE = "No FerryAnnouncement found"

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig()
        ),
        vol.Required(CONF_FROM): selector.TextSelector(selector.TextSelectorConfig()),
        vol.Optional(CONF_TO): selector.TextSelector(selector.TextSelectorConfig()),
        vol.Optional(CONF_TIME): selector.TimeSelector(selector.TimeSelectorConfig()),
        vol.Required(CONF_WEEKDAY, default=WEEKDAYS): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=WEEKDAYS,
                multiple=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)
DATA_SCHEMA_REAUTH = vol.Schema(
    {
        vol.Required(CONF_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig()
        ),
    }
)


class TVFerryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafikverket Ferry integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry | None

    async def validate_input(
        self, api_key: str, ferry_from: str, ferry_to: str
    ) -> None:
        """Validate input from user input."""
        web_session = async_get_clientsession(self.hass)
        ferry_api = TrafikverketFerry(web_session, api_key)
        await ferry_api.async_get_next_ferry_stop(ferry_from, ferry_to)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication with Trafikverket."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Trafikverket."""
        errors: dict[str, str] = {}

        if user_input:
            api_key = user_input[CONF_API_KEY]

            assert self.entry is not None
            try:
                await self.validate_input(
                    api_key, self.entry.data[CONF_FROM], self.entry.data[CONF_TO]
                )
            except ValueError as err:
                if str(err) == ERROR_INVALID_AUTH:
                    errors["base"] = "invalid_auth"
                elif str(err) == ERROR_INVALID_ROUTE:
                    errors["base"] = "invalid_route"
                else:
                    errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_API_KEY: api_key,
                    },
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA_REAUTH,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key: str = user_input[CONF_API_KEY]
            ferry_from: str = user_input[CONF_FROM]
            ferry_to: str = user_input.get(CONF_TO, "")
            ferry_time: str = user_input[CONF_TIME]
            weekdays: list[str] = user_input[CONF_WEEKDAY]

            name = f"{ferry_from}"
            if ferry_to:
                name = name + f" to {ferry_to}"
            if ferry_time != "00:00:00":
                name = name + f" at {str(ferry_time)}"

            try:
                await self.validate_input(api_key, ferry_from, ferry_to)
            except ValueError as err:
                if str(err) == ERROR_INVALID_AUTH:
                    errors["base"] = "invalid_auth"
                elif str(err) == ERROR_INVALID_ROUTE:
                    errors["base"] = "invalid_route"
                else:
                    errors["base"] = "cannot_connect"
            else:
                if not errors:
                    unique_id = create_unique_id(
                        ferry_from,
                        ferry_to,
                        ferry_time,
                        weekdays,
                    )
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=name,
                        data={
                            CONF_API_KEY: api_key,
                            CONF_NAME: name,
                            CONF_FROM: ferry_from,
                            CONF_TO: ferry_to,
                            CONF_TIME: ferry_time,
                            CONF_WEEKDAY: weekdays,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
