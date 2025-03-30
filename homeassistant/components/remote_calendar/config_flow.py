"""Config flow for Remote Calendar integration."""

import logging
from typing import Any

from httpx import HTTPError, InvalidURL
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_CALENDAR_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_NAME): str,
        vol.Required(CONF_URL): str,
    }
)


class RemoteCalendarConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remote Calendar."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        errors: dict = {}
        _LOGGER.debug("User input: %s", user_input)
        self._async_abort_entries_match(
            {CONF_CALENDAR_NAME: user_input[CONF_CALENDAR_NAME]}
        )
        if user_input[CONF_URL].startswith("webcal://"):
            user_input[CONF_URL] = user_input[CONF_URL].replace(
                "webcal://", "https://", 1
            )
        self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
        client = get_async_client(self.hass)
        try:
            res = await client.get(user_input[CONF_URL], follow_redirects=True)
            res.raise_for_status()
        except (HTTPError, InvalidURL) as err:
            errors["base"] = "cannot_connect"
            _LOGGER.debug("An error occurred: %s", err)
        else:
            try:
                await self.hass.async_add_executor_job(
                    IcsCalendarStream.calendar_from_ics, res.text
                )
            except CalendarParseError as err:
                errors["base"] = "invalid_ics_file"
                _LOGGER.debug("Invalid .ics file: %s", err)
            else:
                return self.async_create_entry(
                    title=user_input[CONF_CALENDAR_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
