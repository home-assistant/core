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


async def _validate_host(flow: GoogleWifiConfigFlow, host: str) -> dict[str, str]:
    """Validate the host."""
    try:
        await GoogleWifiAPI(
            host, sess=async_get_clientsession(flow.hass)
        ).async_update()
    except GoogleWifiClientError:
        return {"base": "cannot_connect"}
    except GoogleWifiDataValidationError:
        return {"base": "unknown"}
    return {}


class GoogleWifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Wifi."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host: str | None = user_input[CONF_HOST]
            if host is None:
                return self.async_show_form(
                    step_id="user",
                    data_schema=CONFIG_SCHEMA,
                    errors={"host": "invalid_host"},
                )
            if (errors := await _validate_host(self, host)) == {}:
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title="Google Wifi", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reconfigure step."""
        errors: dict = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            if (errors := await _validate_host(self, host)) == {}:
                self._async_abort_entries_match({CONF_HOST: host})
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reconfigure", data_schema=CONFIG_SCHEMA, errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import of configuration from YAML."""
        host = import_data[CONF_HOST]
        name = import_data.get(CONF_NAME, "Google Wifi")

        errors = await _validate_host(self, host)
        if errors != {}:
            return self.async_abort(reason=errors["base"])

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
