"""Config flow to allow modbus create a config_entry."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_METHOD, CONF_NAME

from .const import MODBUS_DOMAIN


class ModbusConfigFlow(ConfigFlow, domain=MODBUS_DOMAIN):
    """modbus integration config flow."""

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from configuration.yaml.

        One import step occurs for each Modbus hub defined in the configuration.
        """
        for entry in self.hass.config_entries.async_entries(MODBUS_DOMAIN):
            if (
                entry.data[CONF_NAME] == import_data[CONF_NAME]
                or entry.data[CONF_METHOD] == import_data[CONF_METHOD]
            ):
                self.hass.config_entries.async_update_entry(entry, data=import_data)
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=import_data[CONF_NAME],
            data=import_data,
        )
