"""Config flow to configure firmata component."""

import logging

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback

from .board import get_board
from .const import CONF_SERIAL_PORT, DOMAIN  # pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)


@callback
def configured_boards(hass: HomeAssistant) -> dict:
    """Return a set of all configured boards."""
    return {
        entry.data[CONF_NAME]: entry
        for entry in hass.config_entries.async_entries(DOMAIN)
    }


class FirmataFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a firmata config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config: dict):
        """Import a firmata board as a config entry.

        This flow is triggered by `async_setup` for configured boards.

        This will execute for any board that does not have a
        config entry yet (based on entry_id). It validates a connection
        and then adds the entry.
        """
        name = f"serial-{import_config[CONF_SERIAL_PORT]}"
        import_config[CONF_NAME] = name

        # Connect to the board to verify connection and then shutdown
        # If either fail then we cannot continue
        _LOGGER.debug("Connecting to Firmata board %s to test connection", name)
        try:
            api = await get_board(import_config)
            await api.shutdown()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error connecting to PyMata board %s: %s", name, err)
            return self.async_abort(reason="cannot_connect")
        _LOGGER.debug("Connection test to Firmata board %s successful", name)

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )
