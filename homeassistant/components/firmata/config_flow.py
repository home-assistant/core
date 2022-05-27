"""Config flow to configure firmata component."""

import logging
from typing import Any

from pymata_express.pymata_express_serial import serial

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .board import get_board
from .const import CONF_SERIAL_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FirmataFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a firmata config flow."""

    VERSION = 1

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
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
        except RuntimeError as err:
            _LOGGER.error("Error connecting to PyMata board %s: %s", name, err)
            return self.async_abort(reason="cannot_connect")
        except serial.serialutil.SerialTimeoutException as err:
            _LOGGER.error(
                "Timeout writing to serial port for PyMata board %s: %s", name, err
            )
            return self.async_abort(reason="cannot_connect")
        except serial.serialutil.SerialException as err:
            _LOGGER.error(
                "Error connecting to serial port for PyMata board %s: %s", name, err
            )
            return self.async_abort(reason="cannot_connect")
        _LOGGER.debug("Connection test to Firmata board %s successful", name)

        return self.async_create_entry(
            title=import_config[CONF_NAME], data=import_config
        )
