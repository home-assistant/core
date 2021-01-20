"""Config flow for workday integration."""
import datetime
import logging

import holidays
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify

from .const import (
    ALLOWED_DAYS,
    CONF_ADD_HOLIDAYS,
    CONF_ADVANCED,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_STATE,
    CONF_SUBCOUNTRY,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_NAME,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
    ERR_NO_COUNTRY,
    ERR_NO_SUBCOUNTRY,
)

_LOGGER = logging.getLogger(__name__)


SCHEMA_ADVANCED = {
    vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): vol.Coerce(int),
    vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS): cv.multi_select(
        ALLOWED_DAYS
    ),
    vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES): cv.multi_select(
        ALLOWED_DAYS
    ),
}

OPTIONS_ACTION = "options_action"
ACTION_ADD_HOLIDAYS = "ADD_HOLIDAYS"
ACTION_REMOVE_HOLIDAYS = "REMOVE_HOLIDAYS"
CONF_NEW_HOLIDAY = "new_holiday"
CONF_HOLIDAY_TO_REMOVE = "holiday_to_remove"


async def validate_input(data, errors):
    """Validate the user input data.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    country = data[CONF_COUNTRY]
    subcountry = data.get(CONF_SUBCOUNTRY)

    all_supported_countries = holidays.list_supported_countries()
    year = datetime.datetime.now().year
    obj_holidays = getattr(holidays, country)(years=year)

    if country not in all_supported_countries:
        errors[CONF_COUNTRY] = ERR_NO_COUNTRY
        return

    if subcountry:
        # 'state' and 'prov' are not interchangeable, so need to make
        # sure we use the right one
        if hasattr(obj_holidays, "PROVINCES") and subcountry in obj_holidays.PROVINCES:
            province = subcountry
            state = None
        elif hasattr(obj_holidays, "STATES") and subcountry in obj_holidays.STATES:
            province = None
            state = subcountry
        else:
            _LOGGER.error(
                "There is no province/state %s in country %s", subcountry, country
            )
            errors[CONF_SUBCOUNTRY] = ERR_NO_SUBCOUNTRY
            return
    else:
        province = None
        state = None
    title = f"Workday {country}{f' ({subcountry})' if subcountry is not None else ''}"
    return {"title": title, "province": province, "state": state}


class WorkdayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for workday."""

    VERSION = 1
    # TODO pick one of the available connection classes in homeassistant/config_entries.py
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    _countries = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return WorkdayOptionsFlow(config_entry)

    def __init__(self):
        """Initialize flow instance."""
        self._title = None
        self._init_info = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if self._countries is None:
            self._countries = {}
            for case in sorted(
                holidays.list_supported_countries(), key=lambda case: case
            ):
                if len(case) > 3:
                    self._countries[case] = case
            # self._countries = holidays.list_supported_countries()

        if user_input is not None:
            info = await validate_input(user_input, errors)

            if info is not None:
                unique_id = slugify(info["title"])
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                user_input[CONF_PROVINCE] = info["province"]
                user_input[CONF_STATE] = info["state"]
                user_input[CONF_NAME] = info["title"]
                self._title = info["title"]

                if user_input.get(CONF_ADVANCED):
                    self._init_info = user_input
                    return await self.async_step_advanced_conf()

                user_input[CONF_WORKDAYS] = DEFAULT_WORKDAYS
                user_input[CONF_EXCLUDES] = DEFAULT_EXCLUDES
                user_input[CONF_OFFSET] = DEFAULT_OFFSET
                return self.async_create_entry(title=self._title, data=user_input)

        previous_input = user_input or {}
        _LOGGER.info("previous_input %s", previous_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COUNTRY,
                        description={
                            "suggested_value": previous_input.get(CONF_COUNTRY)
                        },
                    ): vol.In(self._countries),
                    vol.Optional(
                        CONF_SUBCOUNTRY,
                        description={
                            "suggested_value": previous_input.get(CONF_SUBCOUNTRY)
                        },
                    ): str,
                    vol.Optional(
                        CONF_ADVANCED,
                        description={
                            "suggested_value": previous_input.get(CONF_ADVANCED)
                        },
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_advanced_conf(self, user_input=None):
        """Handle the advanced configuration step."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._title, data={**user_input, **self._init_info}
            )

        return self.async_show_form(
            step_id="advanced_conf",
            data_schema=vol.Schema(SCHEMA_ADVANCED),
        )

    async def async_step_import(self, device_config):
        """Import a configuration.yaml config.

        This flow is triggered by `async_setup` for configured panels.
        """
        _LOGGER.debug("async_step_import: %s", device_config)
        data = {}
        errors = {}

        data[CONF_COUNTRY] = device_config.get(CONF_COUNTRY)
        data[CONF_SUBCOUNTRY] = device_config.get(CONF_PROVINCE)
        data[CONF_WORKDAYS] = device_config.get(CONF_WORKDAYS, DEFAULT_WORKDAYS)
        data[CONF_EXCLUDES] = device_config.get(CONF_EXCLUDES, DEFAULT_EXCLUDES)
        data[CONF_OFFSET] = device_config.get(CONF_OFFSET, DEFAULT_OFFSET)
        data[CONF_NAME] = device_config.get(CONF_NAME, DEFAULT_NAME)
        conf_add = device_config.get(CONF_ADD_HOLIDAYS)
        if conf_add:
            data[CONF_ADD_HOLIDAYS] = conf_add
        conf_remove = device_config.get(CONF_REMOVE_HOLIDAYS)
        if conf_remove:
            data[CONF_REMOVE_HOLIDAYS] = conf_remove

        info = await validate_input(data, errors)

        if info is not None:
            unique_id = slugify(info["title"])
            _LOGGER.debug("unique_id: %s", unique_id)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            data[CONF_PROVINCE] = info["province"]
            data[CONF_STATE] = info["state"]
            self._title = info["title"]
            self._init_info = data
        else:
            return self.async_abort(reason="config_cannot_be_imported")

        return await self.async_step_import_confirm()

    async def async_step_import_confirm(self, user_input=None):
        """Confirm the user wants to import the config entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="import_confirm",
                description_placeholders={"id": self._title},
            )

        return self.async_create_entry(title=self._title, data=self._init_info)


class WorkdayOptionsFlow(config_entries.OptionsFlow):
    """Handle Workday options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Workday options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_prompt_options(user_input)

    async def async_step_prompt_options(self, user_input=None):
        """Prompt for options."""
        errors = {}

        if user_input is not None:
            action = user_input[OPTIONS_ACTION]
            _LOGGER.debug("action: %s", action)
            if action == ACTION_ADD_HOLIDAYS:
                return await self.async_step_add_holidays()
            if action == ACTION_REMOVE_HOLIDAYS:
                return await self.async_step_remove_holidays()
            errors[OPTIONS_ACTION] = "unsupported_action"

        return self.async_show_form(
            step_id="prompt_options",
            data_schema=vol.Schema(
                {
                    vol.Required(OPTIONS_ACTION): vol.In(
                        {
                            ACTION_ADD_HOLIDAYS: "Manage additional holidays",
                            ACTION_REMOVE_HOLIDAYS: "Manage excluded holidays",
                        }
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_add_holidays(self, user_input=None):
        """Manage extra holidays."""
        errors = {}
        data_schema = vol.Schema({})
        _LOGGER.debug("async_step_add_holidays: init...")

        if user_input is None:
            holidays_to_add = self._config_entry.options.get(CONF_ADD_HOLIDAYS, [])
            _LOGGER.debug("holidays_to_add: %s", holidays_to_add)
        else:
            new_holiday = user_input.get(CONF_NEW_HOLIDAY)
            holidays_to_add = user_input.get(CONF_ADD_HOLIDAYS, [])
            _LOGGER.debug("new_holiday: %s", new_holiday)
            _LOGGER.debug("holidays_to_add: %s", holidays_to_add)
            if new_holiday:
                try:
                    cv.date(new_holiday)  # just validate format
                    holidays_to_add.append(new_holiday)
                except vol.Invalid:
                    _LOGGER.error("bad format: %s", new_holiday)
                    errors[CONF_NEW_HOLIDAY] = "bad_date_format"
            else:
                holidays_to_add.sort(reverse=True)
                return self._save_config(user_input)

        if holidays_to_add:
            _LOGGER.debug("holidays_to_add")
            data_schema = data_schema.extend(
                {
                    vol.Optional(
                        CONF_ADD_HOLIDAYS, default=holidays_to_add
                    ): cv.multi_select(holidays_to_add),
                }
            )

        # holiday_format = '%Y-%m-%d'
        data_schema = data_schema.extend(
            {
                # vol.Required(CONF_NEW_HOLIDAY, default="123456"): cv.matches_regex("[0-9a-f]{12}"),
                # vol.Optional(CONF_NEW_HOLIDAY): cv.matches_regex("([12]\\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01]))"),
                # vol.Optional(CONF_NEW_HOLIDAY): vol.Any("", cv.matches_regex("([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))")),
                # vol.Optional(CONF_NEW_HOLIDAY): vol.All(str, cv.matches_regex("([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))")),
                # vol.Optional(CONF_NEW_HOLIDAY): cv.date,
                # vol.Optional(CONF_NEW_HOLIDAY): lambda v: datetime.datetime.strptime(v, holiday_format),
                # vol.Optional(CONF_NEW_HOLIDAY): vol.All(str, lambda v: datetime.datetime.strptime(v, holiday_format)),
                # vol.Optional(CONF_NEW_HOLIDAY): vol.Date(format=holiday_format),
                # vol.Optional(CONF_NEW_HOLIDAY): vol.All(str, vol.Date(format=holiday_format)),
                vol.Optional(CONF_NEW_HOLIDAY): str,
            }
        )

        return self.async_show_form(
            step_id="add_holidays", data_schema=data_schema, errors=errors
        )

    async def async_step_remove_holidays(self, user_input=None):
        """Manage holidays to remove."""
        errors = {}
        data_schema = vol.Schema({})

        if user_input is None:
            holidays_to_remove = self._config_entry.options.get(
                CONF_REMOVE_HOLIDAYS, []
            )
        else:
            remove_holiday = user_input.get(CONF_HOLIDAY_TO_REMOVE)
            holidays_to_remove = user_input.get(CONF_REMOVE_HOLIDAYS, [])
            _LOGGER.debug("remove_holiday: %s", remove_holiday)
            _LOGGER.debug("holidays_to_remove: %s", holidays_to_remove)
            if remove_holiday:
                try:
                    cv.date(remove_holiday)  # just validate format
                    holidays_to_remove.append(remove_holiday)
                except vol.Invalid:
                    _LOGGER.error("bad format: %s", remove_holiday)
                    errors[CONF_HOLIDAY_TO_REMOVE] = "bad_date_format"
            else:
                holidays_to_remove.sort(reverse=True)
                return self._save_config(user_input)

        if holidays_to_remove:
            _LOGGER.debug("holidays_to_remove")
            data_schema = data_schema.extend(
                {
                    vol.Optional(
                        CONF_REMOVE_HOLIDAYS, default=holidays_to_remove
                    ): cv.multi_select(holidays_to_remove),
                }
            )

        data_schema = data_schema.extend(
            {
                # vol.Optional(CONF_HOLIDAY_TO_REMOVE): vol.Any("", cv.matches_regex("([12]\d{3}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]))")),
                vol.Optional(CONF_HOLIDAY_TO_REMOVE): str,
            }
        )

        return self.async_show_form(
            step_id="remove_holidays", data_schema=data_schema, errors=errors
        )

    def _save_config(self, data):
        """Save the updated options."""
        curr_conf = self._config_entry.options.copy()
        curr_conf.update(data)

        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self._config_entry.entry_id)
        )

        return self.async_create_entry(title=self._config_entry.title, data=curr_conf)
