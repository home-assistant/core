"""Config flow to configure the LCN integration."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN


@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, info):
        """Import existing configuration from LCN."""
        # check if we already have a host with the same name configured
        host_name = info.pop(CONF_HOST)
        entry = await self.async_set_unique_id(host_name)
        if entry:
            entry.source = config_entries.SOURCE_IMPORT
            self.hass.config_entries.async_update_entry(entry, data=info)
            return self.async_abort(reason="existing_configuration_updated")

        return self.async_create_entry(
            title=f"{host_name}",
            data=info,
        )
