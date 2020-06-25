"""Config flow to configure firmata component."""

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import CONF_SERIAL_PORT, DOMAIN


@callback
def configured_boards(hass):
    """Return a set of all configured boards."""
    return {
        entry.data[CONF_NAME]: entry
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


@config_entries.HANDLERS.register(DOMAIN)
class FirmataFlowHandler(config_entries.ConfigFlow):
    """Handle a firmata config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config):
        """Import a firmata board as a config entry.

        This flow is triggered by `async_setup` for configured boards.
        This flow is also triggered by `async_step_discovery`.

        This will execute for any board that does not have a
        config entry yet (based on entry_id).
        """
        name = f"serial-{import_config[CONF_SERIAL_PORT]}"
        import_config[CONF_NAME] = name

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )
