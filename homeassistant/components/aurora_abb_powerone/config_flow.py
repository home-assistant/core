"""Config flow for Aurora ABB PowerOne integration."""
import logging

from aurorapy.client import AuroraError, AuroraSerialClient
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_ADDRESS, CONF_PORT  # CONF_NAME,

from .const import CONF_CONNECTNOW, DEFAULT_ADDRESS, MAX_ADDRESS, MIN_ADDRESS

from .const import DOMAIN  # DEFAULT_NAME,; pylint:disable=unused-import

# import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)


async def validate_comport(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.
    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth
    print(data)
    comport = data[CONF_PORT]
    address = data[CONF_ADDRESS]
    _LOGGER.debug("Intitialising com port=%s", comport)
    try:
        client = AuroraSerialClient(address, comport, parity="N", timeout=1)
        client.connect()
        sn = client.serial_number()
        print(f"sn='{sn}'")
    except AuroraError as e:
        _LOGGER.warn("Could not connect to device=%s", comport)
        raise e

    # Return some info we want to store in the config entry.
    return {"title": "Aurora ABB PowerOne Solar Inverter"}


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
        print(errors)
        if self._comportslist is None:
            comports = serial.tools.list_ports.comports(include_links=True)
            comportslist = []
            for port in comports:
                comportslist.append(port.device)
                print(port.device)
            if len(comportslist) > 0:
                defaultcomport = comportslist[0]
            else:
                print("No COM ports found")
                defaultcomport = "No COM ports found"
            self._comportslist = comportslist
            self._defaultcomport = defaultcomport

        # Handle the initial step.
        if user_input is not None:
            # try:
            self.config = {
                CONF_PORT,
                CONF_ADDRESS,
            }
            if user_input[CONF_CONNECTNOW]:
                try:
                    info = await validate_comport(self.hass, user_input)
                    return self.async_create_entry(title=info["title"], data=user_input)

                except OSError as error:
                    if "no such device" in str(error):
                        errors["base"] = "invalid_serial_port"
                    else:
                        raise error
                except AuroraError as error:
                    if "could not open port" in str(error):
                        _LOGGER.error("Unable to open serial port")
                        errors["base"] = "cannot_open_serial_port"
                    elif "No response after" in str(error):
                        _LOGGER.error("No response from inverter (could be dark)")
                        errors["base"] = "cannot_connect"
                    else:
                        _LOGGER.error(
                            "Unable to communicate with Aurora ABB Inverter at {}: {} {}".format(
                                user_input[CONF_PORT], type(error), error
                            )
                        )
                        raise error
            else:
                return self.async_create_entry(title="Solar Inverter", data=user_input)

            # except CannotConnect:
            #     errors["base"] = "cannot_connect"
            # except InvalidAuth:
            #     errors["base"] = "invalid_auth"
            # except Exception:  # pylint: disable=broad-except
            #     _LOGGER.exception("Unexpected exception")
            #     errors["base"] = "unknown"

        # DATA_SCHEMA = vol.Schema({"host": str, "username": str, "password": str})
        DATA_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_PORT, default=self._defaultcomport): vol.In(
                    self._comportslist
                ),
                vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): vol.In(
                    range(MIN_ADDRESS, MAX_ADDRESS + 1)
                ),
                vol.Required(CONF_CONNECTNOW, default=True): bool,
                # vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
