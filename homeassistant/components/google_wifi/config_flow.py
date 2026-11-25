"""Config flow for Google Wifi integration."""

from typing import Any, override

from googlewifiapi import GoogleWifiAPI
from googlewifiapi.exception import GoogleWifiClientError, GoogleWifiDataValidationError

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .sensor import CONFIG_SCHEMA, SENSOR_KEYS


class GoogleWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Wifi."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                await GoogleWifiAPI(
                    host, sess=async_get_clientsession(self.hass)
                ).async_update()
            except GoogleWifiClientError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=CONFIG_SCHEMA,
                    errors={"base": "cannot_connect"},
                )
            except GoogleWifiDataValidationError:
                return self.async_show_form(
                    step_id="user",
                    data_schema=CONFIG_SCHEMA,
                    errors={"base": "unknown"},
                )

            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            return self.async_create_entry(title="Google Wifi", data=user_input)

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import of configuration from YAML."""
        host = import_data[CONF_HOST]
        name = import_data.get(CONF_NAME, "Google Wifi")

        try:
            await GoogleWifiAPI(
                host, sess=async_get_clientsession(self.hass)
            ).async_update()
        except GoogleWifiClientError:
            return self.async_abort(reason="cannot_connect")
        except GoogleWifiDataValidationError:
            return self.async_abort(reason="unknown")

        self._async_abort_entries_match({CONF_HOST: host})
        return self.async_create_entry(
            title=name,
            data={
                CONF_HOST: host,
                CONF_NAME: name,
                CONF_MONITORED_CONDITIONS: import_data.get(
                    CONF_MONITORED_CONDITIONS, SENSOR_KEYS
                ),
            },
        )
