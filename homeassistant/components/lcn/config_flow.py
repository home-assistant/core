"""Config flow to configure the LCN integration."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_PORT

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, data):
        """Import existing configuration from LCN."""
        # check if we already have a host with the same name configured
        host_name = data.pop(CONF_HOST)
        unique_id = f"{data[CONF_IP_ADDRESS]}:{data[CONF_PORT]}"
        entry = await self.async_set_unique_id(unique_id)
        if entry:
            entry.source = config_entries.SOURCE_IMPORT
            self.hass.config_entries.async_update_entry(entry, data=data)
            return self.async_abort(reason="existing_configuration_updated")

        return self.async_create_entry(
            title=f"{host_name}",
            data=data,
        )
