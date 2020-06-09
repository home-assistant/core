"""Config flow for Aurora ABB PowerOne integration."""
import logging
from logging import DEBUG

from aurorapy.client import AuroraError, AuroraSerialClient
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_ADDRESS, CONF_PORT

# pylint doesn't think DOMAIN is used.  But it is used!
# Might be this bug? https://github.com/PyCQA/pylint/issues/3445
# pylint: disable=unused-import
from .const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    CONF_USEDUMMYONFAIL,
    DEFAULT_ADDRESS,
    DEFAULT_INTEGRATION_TITLE,
    DOMAIN,
    MAX_ADDRESS,
    MIN_ADDRESS,
)

_LOGGER = logging.getLogger(__name__)


def validate_and_connect(hass: core.HomeAssistant, data, populate_on_fail: False):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    comport = data[CONF_PORT]
    address = data[CONF_ADDRESS]
    _LOGGER.debug("Intitialising com port=%s", comport)
    ret = {}
    ret["title"] = DEFAULT_INTEGRATION_TITLE
    try:
        client = AuroraSerialClient(address, comport, parity="N", timeout=1)
        client.connect()
        ret[ATTR_SERIAL_NUMBER] = client.serial_number()
        ver = client.version()
        partnum = client.pn()
        ret[ATTR_MODEL] = f"{ver} ({partnum})"
        ret[ATTR_FIRMWARE] = client.firmware(1)
        _LOGGER.info("Returning device info=%s", ret)
    except AuroraError as err:
        _LOGGER.warning("Could not connect to device=%s", comport)
        if populate_on_fail:
            ret = {
                "title": DEFAULT_INTEGRATION_TITLE,
                "serial_number": "735492",
                "pn": "-3G97-",
                "firmware": "C.0.3.5",
            }
            _LOGGER.warning("Using dummy device info=%s", ret)
        else:
            raise err
    finally:
        if client.serline.isOpen:
            client.close()

    # Return info we want to store in the config entry.
    return ret


class AuroraABBConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aurora ABB PowerOne."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL
    _comportslist = None
    _defaultcomport = None

    def __init__(self):
        """Initialise the config flow."""
        self.config = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialised by the user."""

        errors = {}
        if self._comportslist is None:
            comports = serial.tools.list_ports.comports(include_links=True)
            comportslist = []
            for port in comports:
                comportslist.append(port.device)
                _LOGGER.debug("COM port option: %s", port.device)
            if len(comportslist) > 0:
                defaultcomport = comportslist[0]
            else:
                _LOGGER.warning(
                    "No com ports found.  Need a valid RS485 device to communicate."
                )
                defaultcomport = "No COM ports found"
            self._comportslist = comportslist
            self._defaultcomport = defaultcomport

        # Handle the initial step.
        if user_input is not None:
            try:
                info = validate_and_connect(
                    self.hass, user_input, user_input.get(CONF_USEDUMMYONFAIL, False)
                )
                info.update(user_input)
                # Bomb out early if someone has already set up this device.
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=info)

            except OSError as error:
                if "no such device" in str(error):
                    errors["base"] = "invalid_serial_port"
            except AuroraError as error:
                if "could not open port" in str(error):
                    _LOGGER.error("Unable to open serial port")
                    errors["base"] = "cannot_open_serial_port"
                elif "No response after" in str(error):
                    _LOGGER.error("No response from inverter (could be dark)")
                    errors["base"] = "cannot_connect"
                else:
                    _LOGGER.error(
                        "Unable to communicate with Aurora ABB Inverter at %s: %s %s",
                        user_input[CONF_PORT],
                        type(error),
                        error,
                    )
                    errors["base"] = "cannot_connect"
        # If no user input, must be first pass through the config.  Show  initial form.
        config_options = {
            vol.Required(CONF_PORT, default=self._defaultcomport): vol.In(
                self._comportslist
            ),
            vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): vol.In(
                range(MIN_ADDRESS, MAX_ADDRESS + 1)
            ),
        }
        # Only show the debug option if debugging is active.
        if _LOGGER.level == DEBUG:
            config_options[vol.Required(CONF_USEDUMMYONFAIL, default=False)] = bool
        schema = vol.Schema(config_options)

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
