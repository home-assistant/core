"""Config flow to configure caldav."""
from __future__ import annotations

import logging
from typing import Any

from caldav.lib.error import DAVError
import voluptuous as vol
from yarl import URL as yurl

from homeassistant import config_entries
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from . import async_caldav_connect
from .const import (
    CONF_CALENDAR,
    CONF_CALENDAR_DELETE,
    CONF_CALENDAR_ID,
    CONF_CALENDAR_NEW_ID,
    CONF_CALENDAR_UP_ID,
    CONF_CALENDARS,
    CONF_CUSTOM_CALENDARS,
    CONF_DAYS,
    CONF_SEARCH,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        # pylint: disable=no-value-for-parameter
        vol.Required(CONF_USERNAME): selector.TextSelector(),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
        vol.Required(CONF_URL): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.URL)
        ),
        vol.Optional(
            CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL
        ): selector.BooleanSelector(),
        vol.Optional(CONF_DAYS, default=1): cv.positive_int,
    }
)

_LOGGER = logging.getLogger(__name__)


class CaldavFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a caldav config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.user_input = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get option flow."""
        return CaldavOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_USERNAME: user_input[CONF_USERNAME],
                    CONF_URL: user_input[CONF_URL],
                }
            )

            try:
                await async_caldav_connect(self.hass, user_input)
                url = yurl(user_input[CONF_URL])
            except DAVError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"{url.host} ({user_input[CONF_USERNAME]})",
                    data=user_input,
                    options={
                        CONF_CALENDARS: user_input.get(CONF_CALENDARS, []),
                        CONF_CUSTOM_CALENDARS: user_input.get(
                            CONF_CUSTOM_CALENDARS, []
                        ),
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)


class CaldavOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle option."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Init object."""
        self.config_entry = config_entry
        calendars = config_entry.options.get(CONF_CUSTOM_CALENDARS, [])
        self._calendars: list = calendars.copy()
        self._conf_calendar_id: int | None = None

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            if sel_calendars := user_input.get(CONF_CUSTOM_CALENDARS):
                return await self.async_step_calendars(None, sel_calendars)
            return self._save_config(user_input)

        return self._async_init_form()

    @callback
    def _save_config(self, data: dict[str, Any]) -> FlowResult:
        """Save the updated options."""
        new_data = {k: v for k, v in data.items() if k not in [CONF_CUSTOM_CALENDARS]}
        if self._calendars:
            new_data[CONF_CUSTOM_CALENDARS] = self._calendars

        return self.async_create_entry(title="", data=new_data)

    @callback
    def _async_init_form(self) -> FlowResult:
        """Handle a flow initialized by the user."""
        inc = 0
        calendars_list: dict = {}
        for _calendar in self._calendars:
            inc += 1
            calendars_list.update({inc: f"{_calendar.get(CONF_NAME)}"})
        options = self.config_entry.options

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CALENDARS,
                    description={"suggested_value": options.get(CONF_CALENDARS)},
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[], custom_value=True, multiple=True
                    )
                ),
                vol.Optional(CONF_CUSTOM_CALENDARS): vol.In(
                    {CONF_CALENDAR_NEW_ID: "Add calendar", **calendars_list}
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)

    async def async_step_calendars(
        self, user_input: dict[str, Any] | None = None, calendar_id: int | None = None
    ) -> FlowResult:
        """Handle options flow for apps list."""
        if calendar_id is not None:
            self._conf_calendar_id = (
                calendar_id if str(calendar_id) != CONF_CALENDAR_NEW_ID else None
            )
            return self._async_calendars_form(calendar_id)

        if user_input is not None:
            calendar_id = user_input.get(CONF_CALENDAR_ID, self._conf_calendar_id)
            if calendar_id:
                if user_input.get(CONF_CALENDAR_DELETE, False):
                    del self._calendars[calendar_id - 1]
                else:
                    if idx := user_input.get(CONF_CALENDAR_UP_ID):
                        del self._calendars[idx - 1]
                    self._calendars.append(
                        {
                            CONF_NAME: user_input.get(CONF_NAME),
                            CONF_CALENDAR: user_input.get(CONF_CALENDAR),
                            CONF_SEARCH: user_input.get(CONF_SEARCH),
                        }
                    )

        return await self.async_step_init()

    @callback
    def _async_calendars_form(self, calendar_id: int) -> FlowResult:
        """Return configuration form for calendars."""
        if str(calendar_id) == CONF_CALENDAR_NEW_ID:
            item = {}
        else:
            item = self._calendars[calendar_id - 1]

        calendar_schema = {
            vol.Optional(
                CONF_NAME,
                description={"suggested_value": item.get(CONF_NAME)},
            ): str,
            vol.Optional(
                CONF_CALENDAR,
                description={"suggested_value": item.get(CONF_CALENDAR)},
            ): str,
            vol.Optional(
                CONF_SEARCH,
                description={"suggested_value": item.get(CONF_SEARCH)},
            ): str,
        }
        if str(calendar_id) == CONF_CALENDAR_NEW_ID:
            cal_id = int(len(self._calendars) + 1)
            data_schema = vol.Schema(
                {vol.Required(CONF_CALENDAR_ID): cal_id, **calendar_schema}
            )
        else:
            data_schema = vol.Schema(
                {
                    vol.Required(CONF_CALENDAR_UP_ID): calendar_id,
                    **calendar_schema,
                    vol.Optional(CONF_CALENDAR_DELETE, default=False): bool,
                }
            )

        return self.async_show_form(step_id="calendars", data_schema=data_schema)
