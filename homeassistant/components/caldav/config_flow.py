"""Config flow to configure caldav."""
import logging

import caldav
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ADD_CUSTO_CALENDAR,
    CONF_CALENDARS,
    CONF_CUSTOM_CALENDARS,
    CONF_DAYS,
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
        vol.Optional(CONF_CALENDARS, default=[]): selector.SelectSelector(
            selector.SelectSelectorConfig(options=[], custom_value=True, multiple=True),
        ),
        vol.Required(CONF_ADD_CUSTO_CALENDAR, default=False): bool,
    }
)

CUSTOM_CALENDARS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_CUSTOM_CALENDARS,
            description={
                "suggested_value": [
                    {
                        "name": "HomeOffice",
                        "calendar": "Agenda",
                        "search": "HomeOffice",
                    },
                    "# Please clean this example",
                ]
            },
        ): selector.ObjectSelector(),
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

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            if user_input.get(CONF_ADD_CUSTO_CALENDAR):
                return await self.async_step_custom_calendars(user_input)

            try:
                username = user_input.get(CONF_USERNAME)
                password = user_input.get(CONF_PASSWORD)
                options = {
                    CONF_CALENDARS: user_input.pop(CONF_CALENDARS, []),
                    CONF_CUSTOM_CALENDARS: user_input.pop(CONF_CUSTOM_CALENDARS, []),
                }

                client = caldav.DAVClient(
                    url,
                    None,
                    username,
                    password,
                    ssl_verify_cert=user_input[CONF_VERIFY_SSL],
                )
                await self.hass.async_add_executor_job(client.principal)
                return self.async_create_entry(
                    title=DOMAIN, data=user_input, options=options
                )

            except Exception as exception:  # pylint:disable=broad-except
                _LOGGER.error(exception)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_custom_calendars(self, user_input=None):
        """Add custom calendars."""
        errors = {}
        if user_input.get(CONF_ADD_CUSTO_CALENDAR):
            user_input.pop(CONF_ADD_CUSTO_CALENDAR)
            self.user_input = user_input
        elif user_input:
            self.user_input.update(user_input)
            return await self.async_step_user(self.user_input)

        return self.async_show_form(
            step_id="custom_calendars",
            data_schema=CUSTOM_CALENDARS_SCHEMA,
            errors=errors,
        )

    async def async_step_import(self, import_config: dict[str, str]) -> FlowResult:
        """Import a config entry from configuration.yaml."""
        entries = self._async_current_entries()
        if any(x.data[CONF_URL] == import_config[CONF_URL] for x in entries):
            return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)


class CaldavOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle option."""

    def __init__(self, config_entry):
        """Initialize the options flow."""
        self.config_entry = config_entry
        self.calendars = self.config_entry.options.get(CONF_CALENDARS, [])
        self.custom_calendars = self.config_entry.options.get(CONF_CUSTOM_CALENDARS, [])

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CALENDARS, default=self.calendars
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[], custom_value=True, multiple=True
                    ),
                ),
                vol.Optional(
                    CONF_CUSTOM_CALENDARS,
                    default=[],
                    description={"suggested_value": self.custom_calendars},
                ): selector.ObjectSelector(),
            }
        )
        if user_input:
            if (
                len(user_input[CONF_CALENDARS]) > 0
                and len(user_input[CONF_CUSTOM_CALENDARS]) > 0
            ):
                errors["base"] = "choice_custom"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=errors
        )
