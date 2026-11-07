"""Config flow for ZoneMinder."""

import logging
from typing import Any, override

import probatio
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    Timeout as RequestsTimeout,
)

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import ZoneMinderConfigEntry, create_client
from .const import (
    CONF_INCLUDE_ARCHIVED,
    CONF_PATH_ZMS,
    DEFAULT_COMMAND_OFF,
    DEFAULT_COMMAND_ON,
    DEFAULT_INCLUDE_ARCHIVED,
    DEFAULT_PATH,
    DEFAULT_PATH_ZMS,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MONITOR_FUNCTIONS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Optional(CONF_USERNAME): TextSelector(),
        probatio.Optional(probatio.Secret(CONF_PASSWORD)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        probatio.Required(CONF_PATH, default=DEFAULT_PATH): TextSelector(),
        probatio.Required(CONF_PATH_ZMS, default=DEFAULT_PATH_ZMS): TextSelector(),
        probatio.Required(CONF_SSL, default=DEFAULT_SSL): bool,
        probatio.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
    }
)

OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_INCLUDE_ARCHIVED): bool,
        probatio.Required(CONF_COMMAND_ON): SelectSelector(
            SelectSelectorConfig(
                options=list(MONITOR_FUNCTIONS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="monitor_function",
            )
        ),
        probatio.Required(CONF_COMMAND_OFF): SelectSelector(
            SelectSelectorConfig(
                options=list(MONITOR_FUNCTIONS),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="monitor_function",
            )
        ),
    }
)

DEFAULT_OPTIONS = {
    CONF_INCLUDE_ARCHIVED: DEFAULT_INCLUDE_ARCHIVED,
    CONF_COMMAND_ON: DEFAULT_COMMAND_ON,
    CONF_COMMAND_OFF: DEFAULT_COMMAND_OFF,
}


class ZoneMinderConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZoneMinder."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ZoneMinderConfigEntry,
    ) -> ZoneMinderOptionsFlow:
        """Get the options flow for this handler."""
        return ZoneMinderOptionsFlow()

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Log in to ZoneMinder and return an error key on failure."""
        client = create_client(data)
        try:
            logged_in = await self.hass.async_add_executor_job(client.login)
        except RequestsConnectionError, RequestsTimeout:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        if not logged_in:
            return "invalid_auth"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            if (error := await self._async_validate(user_input)) is None:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                    options=DEFAULT_OPTIONS,
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a ZoneMinder server from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        data = {
            key: value
            for key, value in import_data.items()
            if key not in DEFAULT_OPTIONS
        }
        if (error := await self._async_validate(data)) is not None:
            return self.async_abort(reason=error)

        return self.async_create_entry(
            title=data[CONF_HOST],
            data=data,
            options={
                key: import_data.get(key, default)
                for key, default in DEFAULT_OPTIONS.items()
            },
        )


class ZoneMinderOptionsFlow(OptionsFlowWithReload):
    """Handle ZoneMinder options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
        )
