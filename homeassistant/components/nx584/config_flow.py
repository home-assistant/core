"""Config flow for the nx584 integration."""

import logging
from typing import Any, override

from nx584 import client
import requests
import voluptuous as vol
from yarl import URL

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import ObjectSelector
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_EXCLUDE_ZONES,
    CONF_ZONE_TYPES,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    EXCLUDE_ZONES_SCHEMA,
    ZONE_TYPES_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EXCLUDE_ZONES, default=[]): ObjectSelector(),
        vol.Optional(CONF_ZONE_TYPES, default={}): ObjectSelector(),
    }
)


async def _async_validate_connection(hass: HomeAssistant, host: str, port: int) -> None:
    """Raise requests.exceptions.ConnectionError if the panel can't be reached."""
    url = str(URL.build(scheme="http", host=host, port=port))
    alarm_client = client.Client(url)
    await hass.async_add_executor_job(alarm_client.list_zones)


class NX584ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for nx584."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                await _async_validate_connection(
                    self.hass, user_input[CONF_HOST], user_input[CONF_PORT]
                )
            except requests.exceptions.ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_config: ConfigType) -> ConfigFlowResult:
        """Import nx584 config from configuration.yaml."""
        host: str = import_config[CONF_HOST]
        port: int = import_config[CONF_PORT]

        # Only the binary_sensor YAML platform supports exclude_zones/zone_types,
        # and only the alarm_control_panel YAML platform supports name; whichever
        # platform's import runs first creates the entry, so the other platform's
        # import must still be able to apply its own data to it afterwards.
        zone_options: dict[str, Any] | None = None
        if CONF_EXCLUDE_ZONES in import_config:
            zone_options = {
                CONF_EXCLUDE_ZONES: import_config[CONF_EXCLUDE_ZONES],
                CONF_ZONE_TYPES: import_config[CONF_ZONE_TYPES],
            }
        name: str | None = import_config.get(CONF_NAME)

        for entry in self._async_current_entries(include_ignore=False):
            if entry.data[CONF_HOST] != host or entry.data[CONF_PORT] != port:
                continue

            data_updates: dict[str, Any] = {}
            if name is not None and entry.data.get(CONF_NAME, DEFAULT_NAME) != name:
                data_updates[CONF_NAME] = name

            options_updates: dict[str, Any] | None = None
            if zone_options is not None:
                # Options are persisted as JSON, so zone_types keys come back
                # as strings; re-run the schema so the comparison below isn't
                # fooled into reloading the entry on every restart.
                current_zone_types = ZONE_TYPES_SCHEMA(
                    entry.options.get(CONF_ZONE_TYPES, {})
                )
                if (
                    entry.options.get(CONF_EXCLUDE_ZONES, [])
                    != zone_options[CONF_EXCLUDE_ZONES]
                    or current_zone_types != zone_options[CONF_ZONE_TYPES]
                ):
                    options_updates = zone_options

            if data_updates or options_updates is not None:
                update_kwargs: dict[str, Any] = {"reason": "already_configured"}
                if data_updates:
                    update_kwargs["data_updates"] = data_updates
                if options_updates is not None:
                    update_kwargs["options"] = options_updates
                return self.async_update_reload_and_abort(entry, **update_kwargs)
            return self.async_abort(reason="already_configured")

        try:
            await _async_validate_connection(self.hass, host, port)
        except requests.exceptions.ConnectionError:
            return self.async_abort(reason="cannot_connect")
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=host,
            data={CONF_HOST: host, CONF_PORT: port, CONF_NAME: name or DEFAULT_NAME},
            options=zone_options or {},
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> NX584OptionsFlowHandler:
        """Return the options flow."""
        return NX584OptionsFlowHandler()


class NX584OptionsFlowHandler(OptionsFlowWithReload):
    """Handle an options flow for nx584 binary sensor zones."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the exclude_zones and zone_types binary sensor options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                options = {
                    CONF_EXCLUDE_ZONES: EXCLUDE_ZONES_SCHEMA(
                        user_input.get(CONF_EXCLUDE_ZONES, [])
                    ),
                    CONF_ZONE_TYPES: ZONE_TYPES_SCHEMA(
                        user_input.get(CONF_ZONE_TYPES, {})
                    ),
                }
            except vol.Invalid:
                errors["base"] = "invalid_zone_options"
            else:
                return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA, self.config_entry.options
            ),
            errors=errors,
        )
