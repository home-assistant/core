"""Config flow for Aurora ABB PowerOne integration."""
import logging

from aurorapy.client import AuroraError, AuroraSerialClient, AuroraTCPClient
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_PORT, CONF_TYPE

from .const import (
    ATTR_FIRMWARE,
    ATTR_MODEL,
    ATTR_SERIAL_NUMBER,
    DEFAULT_ADDRESS,
    DEFAULT_HOST,
    DEFAULT_INTEGRATION_TITLE,
    DEFAULT_PORT,
    DEFAULT_TYPE,
    DOMAIN,
    MAX_ADDRESS,
    MIN_ADDRESS,
)

# radio buttons are not translated, therefore use identifiers as string.
# https://community.home-assistant.io/t/customize-display-value-of-combobox-items-for-integration-config-flow/284872
CONF_TYPE_SERIAL = "serial"
CONF_TYPE_TCP = "TCP"

_LOGGER = logging.getLogger(__name__)


def schema_serial(comportslist, comportdefault):
    """Create a flow schema for serial mode settings."""
    config_options = {
        vol.Required(CONF_PORT, default=comportdefault): vol.In([comportslist]),
        vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): vol.In(
            range(MIN_ADDRESS, MAX_ADDRESS + 1)
        ),
    }
    return vol.Schema(config_options)


def schema_tcp():
    """Create a config flow schema for TCP mode settings."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): vol.In(
                range(MIN_ADDRESS, MAX_ADDRESS + 1)
            ),
        }
    )


def validate_and_connect(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    if data[CONF_TYPE] == CONF_TYPE_TCP:
        return __validate_and_connect_tcp(hass, data)
    # fallback to serial if nothing is given
    return __validate_and_connect_serial(hass, data)


def __validate_and_connect_serial(hass: core.HomeAssistant, data):
    comport = data[CONF_PORT]
    address = data[CONF_ADDRESS]
    _LOGGER.debug("Intitialising com port=%s", comport)
    ret = {}
    ret["title"] = DEFAULT_INTEGRATION_TITLE
    try:
        client = AuroraSerialClient(address, comport, parity="N", timeout=1)
        client.connect()
        ret[ATTR_SERIAL_NUMBER] = client.serial_number()
        ret[ATTR_MODEL] = f"{client.version()} ({client.pn()})"
        ret[ATTR_FIRMWARE] = client.firmware(1)
        _LOGGER.info("Returning device info=%s", ret)
    except AuroraError as err:
        _LOGGER.warning("Could not connect to device=%s", comport)
        raise err
    finally:
        if client.serline.isOpen():
            client.close()

    # Return info we want to store in the config entry.
    return ret


def __validate_and_connect_tcp(hass: core.HomeAssistant, data):
    host = data[CONF_HOST]
    port = data[CONF_PORT]
    address = data[CONF_ADDRESS]
    _LOGGER.debug("Intitialising connection to %s:%s [%s]", host, port, address)
    ret = {}
    ret["title"] = DEFAULT_INTEGRATION_TITLE
    try:
        client = AuroraTCPClient(host, port, address, timeout=1)
        client.connect()
        ret[ATTR_SERIAL_NUMBER] = client.serial_number()
        ret[ATTR_MODEL] = f"{client.version()} ({client.pn()})"
        ret[ATTR_FIRMWARE] = client.firmware(1)
        _LOGGER.info("Returning device info=%s", ret)
    except AuroraError as err:
        _LOGGER.warning("Could not connect to device %s:%s [%s]", host, port, address)
        raise err
    finally:
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
        return await self.async_step_user_ctype()

    async def async_step_user_ctype(self, user_input=None):
        """Select connection type."""
        errors = {}
        if user_input is not None:
            if user_input.get(CONF_TYPE) == CONF_TYPE_SERIAL:
                if self._comportslist is None:
                    comports = serial.tools.list_ports.comports(include_links=True)
                    comportslist = ["/dev/test"]
                    for port in comports:
                        comportslist.append(port.device)
                        _LOGGER.debug("COM port option: %s", port.device)
                    if len(comportslist) > 0:
                        defaultcomport = comportslist[0]
                    else:
                        _LOGGER.warning(
                            "No com ports found.  Need a valid RS485 device to communicate"
                        )
                        return self.async_abort(reason="no_serial_ports")
                    self._comportslist = comportslist
                    self._defaultcomport = defaultcomport

                return self.async_show_form(
                    step_id="user_serial",
                    data_schema=schema_serial(self._defaultcomport, self._comportslist),
                    errors=errors,
                )
            if user_input.get(CONF_TYPE) == CONF_TYPE_TCP:
                return self.async_show_form(
                    step_id="user_tcp",
                    data_schema=schema_tcp(),
                    errors=errors,
                )
        # If no user input, must be first pass through the config.  Show  initial form.
        config_options = {
            vol.Required(CONF_TYPE, default=DEFAULT_TYPE): vol.In(
                [CONF_TYPE_SERIAL, CONF_TYPE_TCP]
            ),
        }
        schema = vol.Schema(config_options)
        return self.async_show_form(
            step_id="user_ctype", data_schema=schema, errors=errors
        )

    async def async_step_user_serial(self, user_input=None):
        """Handle step 2 (user has selected serial type then entered data)."""

        errors = {}
        if user_input is not None:
            try:
                user_input[CONF_TYPE] = CONF_TYPE_SERIAL
                info = await self.hass.async_add_executor_job(
                    validate_and_connect, self.hass, user_input
                )
                info.update(user_input)
                # Bomb out early if someone has already set up this device.
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=info)

            except AuroraError as error:
                if "Reading Timeout" in str(error):
                    errors["base"] = "cannot_connect"  # could be dark
                else:
                    _LOGGER.error(
                        "Unable to communicate with Aurora ABB Inverter at %s: %s %s",
                        user_input[CONF_PORT],
                        type(error),
                        error,
                    )
                    errors["base"] = "cannot_connect"
        # If we get to here, show the form again (could be no data so far or error).
        return self.async_show_form(
            step_id="user_ctype",
            data_schema=schema_serial(self._defaultcomport, self._comportslist),
            errors=errors,
        )

    async def async_step_user_tcp(self, user_input=None):
        """Handle step 2 (user has selected tcp type then entered data)."""

        errors = {}
        if user_input is not None:
            try:
                user_input[CONF_TYPE] = CONF_TYPE_TCP
                info = await self.hass.async_add_executor_job(
                    validate_and_connect, self.hass, user_input
                )
                info.update(user_input)
                # Bomb out early if someone has already set up this device.
                device_unique_id = info["serial_number"]
                await self.async_set_unique_id(device_unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=info["title"], data=info)

            except OSError as error:
                if error.errno == 19:  # No such device.
                    errors["base"] = "invalid_serial_port"
            except AuroraError as error:
                if "could not open port" in str(error):
                    errors["base"] = "cannot_open_serial_port"
                elif "No response after" in str(error):
                    errors["base"] = "cannot_connect"  # could be dark
                else:
                    _LOGGER.error(
                        "Unable to communicate with Aurora ABB Inverter at %s: %s %s",
                        user_input[CONF_PORT],
                        type(error),
                        error,
                    )
                    errors["base"] = "cannot_connect"
        # If we get to here, show the form again (could be no data so far or error).
        return self.async_show_form(
            step_id="user_ctype",
            data_schema=schema_tcp(),
            errors=errors,
        )
