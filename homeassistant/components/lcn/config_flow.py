"""Config flow to configure the LCN integration."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_PORT

from .const import DOMAIN


def get_config_entry(hass, data):
    """Check config entries for already configured entries based on the ip address/port."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_IP_ADDRESS] == data[CONF_IP_ADDRESS]
            and entry.data[CONF_PORT] == data[CONF_PORT]
        ),
        None,
    )


@config_entries.HANDLERS.register(DOMAIN)
class LcnFlowHandler(config_entries.ConfigFlow):
    """Handle a LCN config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, data):
        """Import existing configuration from LCN."""
        # check if we already have a host with the same address configured
        entry = get_config_entry(self.hass, data)
        host_name = data.pop(CONF_HOST)
        if entry:
            entry.source = config_entries.SOURCE_IMPORT
            self.hass.config_entries.async_update_entry(entry, data=data)
            return self.async_abort(reason="existing_configuration_updated")

        return self.async_create_entry(
            title=f"{host_name}",
            data=data,
        )
