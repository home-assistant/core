"""Config flow to configure firmata component."""

import voluptuous as vol

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

    async def async_step_init(self, user_input=None):
        """Needed in order to not require re-translation of strings."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a firmata config flow start.

        If only one board is found go to link step.
        If more than one board is found let user choose board to link.
        If no board is found allow user to manually input configuration.
        """

        if user_input is not None:
            self.firmata_config = user_input
            return await self._create_entry()

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required(CONF_SERIAL_PORT): str
            }),
        )

#    @staticmethod
#    def serial_ports():
#        """ List possible serial ports.
#        From https://stackoverflow.com/a/14224477"""
#        import glob
#        import sys
#        if sys.platform.startswith('win'):
#            ports = ['COM%s' % (i + 1) for i in range(256)]
#        elif (sys.platform.startswith('linux') or
#              sys.platform.startswith('cygwin')):
#            # this excludes your current terminal "/dev/tty"
#            ports = glob.glob('/dev/tty[A-Za-z]*')
#        elif sys.platform.startswith('darwin'):
#            ports = glob.glob('/dev/tty.*')
#        return ports

    async def _create_entry(self):
        """Create entry for board."""
        if CONF_SERIAL_PORT in self.firmata_config:
            name = self.firmata_config[CONF_SERIAL_PORT]
            if '/' in name:
                name = name.split('/')[-1]
        elif CONF_PORT in self.firmata_config:
            name = (self.firmata_config[CONF_HOST] + '-' +
                    self.firmata_config[CONF_PORT])
        else:
            name = self.firmata_config[CONF_HOST]
        self.firmata_config[CONF_NAME] = name

        return self.async_create_entry(
            title='firmata-' + self.firmata_config[CONF_NAME],
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
