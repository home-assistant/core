"""Config flow to configure firmata component."""

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN, CONF_SERIAL_PORT, CONF_PORT


@callback
def configured_boards(hass):
    """Return a set of all configured boards."""
    return {entry.data[CONF_NAME]: entry for entry
            in hass.config_entries.async_entries(DOMAIN)}


@config_entries.HANDLERS.register(DOMAIN)
class FirmataFlowHandler(config_entries.ConfigFlow):
    """Handle a firmata config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    _hassio_discovery = None

    def __init__(self):
        """Initialize the firmata config flow."""
        self.firmata_config = {}

    async def _create_entry(self):
        """Create entry for board."""
        if CONF_SERIAL_PORT in self.firmata_config:
            name = f"serial-{self.firmata_config[CONF_SERIAL_PORT]}"
        elif CONF_PORT in self.firmata_config:
            name = (f"remote-{self.firmata_config[CONF_HOST]}:"
                    f"{self.firmata_config[CONF_PORT]}")
        else:
            name = self.firmata_config[CONF_HOST]
        self.firmata_config[CONF_NAME] = name

        return self.async_create_entry(
            title=self.firmata_config[CONF_NAME],
            data=self.firmata_config
        )

    async def async_step_import(self, import_config):
        """Import a firmata board as a config entry.

        This flow is triggered by `async_setup` for configured boards.
        This flow is also triggered by `async_step_discovery`.

        This will execute for any board that does not have a
        config entry yet (based on board name).
        """
        self.firmata_config = import_config

        return await self._create_entry()
