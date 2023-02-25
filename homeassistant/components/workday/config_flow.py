"""Config flow for Workday."""
import logging
from types import MappingProxyType
from typing import Any

import holidays
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_COUNTRY, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

# from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from . import util
from .const import (
    ALLOWED_DAYS,
    CONF_ADD_HOLIDAYS,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class WorkdayOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the option flow for Workday."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        """Initialize Workday options flow."""
        _LOGGER.debug(
            "Initializing Workday options flow with ConfigEntry: %s",
            util.config_entry_to_string(entry),
        )
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-initiated configuration."""
        errors: dict[str, str] = {}
        _LOGGER.debug(
            "WorkdayOptionsFlowHandler.async_step_init user_input: %s", user_input
        )

        if user_input is not None:
            try:
                holiday_data = {
                    CONF_NAME: self._entry.unique_id,
                    CONF_COUNTRY: self._entry.data[CONF_COUNTRY],
                }
                holiday_data.update(self._entry.data)
                holiday_data.update(user_input)
                util.build_holidays(holiday_data)
            except util.AddHolidayError:
                errors[CONF_ADD_HOLIDAYS] = "bad_holiday"
            except util.NoSuchHolidayError:
                errors[CONF_REMOVE_HOLIDAYS] = "no_such_holiday"
            else:
                return self.async_create_entry(data=user_input)

        return self._async_show_form(
            step_id="init", user_input=user_input, errors=errors
        )

    @callback
    def _async_show_form(
        self,
        step_id: str,
        user_input: dict[str, Any] | MappingProxyType[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        if user_input is None:
            _LOGGER.debug(
                "No user_input, using default values: %s", self._entry.options
            )
            user_input = self._entry.options

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PROVINCE, default=user_input.get(CONF_PROVINCE, "")
                    ): vol.In(
                        sorted(
                            holidays.list_supported_countries()[
                                self._entry.data[CONF_COUNTRY]
                            ]
                        )
                    ),
                    vol.Optional(
                        CONF_OFFSET, default=user_input.get(CONF_OFFSET, DEFAULT_OFFSET)
                    ): vol.Coerce(int),
                    vol.Optional(
                        CONF_WORKDAYS,
                        default=user_input.get(CONF_WORKDAYS, DEFAULT_WORKDAYS),
                    ): cv.multi_select(ALLOWED_DAYS),
                    vol.Optional(
                        CONF_EXCLUDES,
                        default=user_input.get(CONF_EXCLUDES, DEFAULT_EXCLUDES),
                    ): cv.multi_select(ALLOWED_DAYS),
                    vol.Optional(
                        CONF_ADD_HOLIDAYS, default=user_input.get(CONF_ADD_HOLIDAYS, "")
                    ): cv.string,
                    vol.Optional(
                        CONF_REMOVE_HOLIDAYS,
                        default=user_input.get(CONF_REMOVE_HOLIDAYS, ""),
                    ): cv.string,
                }
            ),
            errors=errors or {},
        )


class WorkdayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Workday config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-initiated configuration."""
        _LOGGER.debug("WorkdayConfigFlow.async_step_user user_input: %s", user_input)
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_NAME])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self._async_show_form(step_id="user", user_input=user_input)

    @callback
    def _async_show_form(
        self,
        step_id: str,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> FlowResult:
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=user_input.get(CONF_NAME, ""),
                    ): cv.string,
                    vol.Required(
                        CONF_COUNTRY,
                        default=user_input.get(CONF_COUNTRY, self.hass.config.country),
                    ): vol.In(sorted(holidays.list_supported_countries().keys())),
                }
            ),
            errors=errors or {},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WorkdayOptionsFlowHandler:
        """Get the options flow for the Workday handler."""
        return WorkdayOptionsFlowHandler(config_entry)
