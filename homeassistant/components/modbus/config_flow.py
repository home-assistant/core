"""Config flow to allow modbus create a config_entry."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import _LOGGER, MODBUS_DOMAIN


class ModbusConfigFlow(ConfigFlow, domain=MODBUS_DOMAIN):
    """modbus integration config flow."""

    async def async_step_import(self, hub: dict[str, Any]) -> ConfigFlowResult:
        """Handle import of a single hub from configuration.yaml."""
        _LOGGER.debug("modbus_cf async_step_import")
        for entry in self.hass.config_entries.async_entries(MODBUS_DOMAIN):
            if entry.data[CONF_NAME] == hub[CONF_NAME] or (
                entry.data.get(CONF_HOST) == hub.get(CONF_HOST)
                and entry.data[CONF_PORT] == hub[CONF_PORT]
            ):
                self.hass.config_entries.async_update_entry(entry, data=hub)
                return self.async_abort(reason="already_configured")
        return self.async_create_entry(
            title=hub[CONF_NAME],
            data=hub,
        )
