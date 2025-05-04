"""Config flow for Remote Calendar integration."""

from http import HTTPStatus
import logging
from typing import Any

from httpx import HTTPError, InvalidURL
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_CALENDAR_NAME, CONF_MIDNIGHT_AS_ALL_DAY, DOMAIN
from .coordinator import RemoteCalendarConfigEntry

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CALENDAR_NAME): str,
        vol.Required(CONF_URL): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MIDNIGHT_AS_ALL_DAY): bool,
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
            if res.status_code == HTTPStatus.FORBIDDEN:
                errors["base"] = "forbidden"
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                )
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
                _LOGGER.error("Error reading the calendar information: %s", err.message)
                _LOGGER.debug(
                    "Additional calendar error detail: %s", str(err.detailed_error)
                )
            else:
                return self.async_create_entry(
                    title=user_input[CONF_CALENDAR_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: RemoteCalendarConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return RemoteCalendarOptionsFlow()


class RemoteCalendarOptionsFlow(OptionsFlow):
    """Handles options flow for the component."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
