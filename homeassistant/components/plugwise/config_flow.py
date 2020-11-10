"""Config flow for Plugwise integration."""
import logging
import os
from typing import Dict

import plugwise
from plugwise.exceptions import (
    InvalidAuthentication,
    NetworkDown,
    PlugwiseException,
    PortError,
    StickInitError,
    TimeoutException,
)
from plugwise.smile import Smile
import serial.tools.list_ports
import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import (
    CONF_BASE,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (  # pylint:disable=unused-import
    CONF_USB_PATH,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FLOW_NET,
    FLOW_TYPE,
    FLOW_USB,
    PW_TYPE,
    SMILE,
    STICK,
    STRETCH,
    ZEROCONF_MAP,
)

_LOGGER = logging.getLogger(__name__)

CONF_MANUAL_PATH = "Enter Manually"

CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(FLOW_TYPE, default=FLOW_NET): vol.In(
            {FLOW_NET: f"Network: {SMILE} / {STRETCH}", FLOW_USB: "USB: Stick"}
        ),
    },
)


@callback
def plugwise_stick_entries(hass):
    """Return existing connections for Plugwise USB-stick domain."""
    sticks = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(PW_TYPE) == STICK:
            sticks.append(entry.data.get(CONF_USB_PATH))
    return sticks


async def validate_usb_connection(self, device_path=None) -> Dict[str, str]:
    """Test if device_path is a real Plugwise USB-Stick."""
    errors = {}
    if device_path is None:
        errors[CONF_BASE] = "connection_failed"
        return errors, None

    # Avoid creating a 2nd connection to an already configured stick
    if device_path in plugwise_stick_entries(self):
        errors[CONF_BASE] = "already_configured"
        return errors, None

    stick = await self.async_add_executor_job(plugwise.stick, device_path)
    try:
        await self.async_add_executor_job(stick.connect)
        await self.async_add_executor_job(stick.initialize_stick)
        await self.async_add_executor_job(stick.disconnect)
    except PortError:
        errors[CONF_BASE] = "cannot_connect"
    except StickInitError:
        errors[CONF_BASE] = "stick_init"
    except NetworkDown:
        errors[CONF_BASE] = "network_down"
    except TimeoutException:
        errors[CONF_BASE] = "network_timeout"
    return errors, stick


def get_serial_by_id(dev_path: str) -> str:
    """Return a /dev/serial/by-id match for given device if available."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return dev_path
    for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
        if os.path.realpath(path) == dev_path:
            return path
    return dev_path


def _base_gw_schema(discovery_info):
    """Generate base schema for gateways."""
    base_gw_schema = {}

    if not discovery_info:
        base_gw_schema[vol.Required(CONF_HOST)] = str
        base_gw_schema[vol.Optional(CONF_PORT, default=DEFAULT_PORT)] = int

    base_gw_schema.update(
        {
            vol.Required(
                CONF_USERNAME, default="smile", description={"suggested_value": "smile"}
            ): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )

    return vol.Schema(base_gw_schema)


async def validate_gw_input(hass: core.HomeAssistant, data):
    """
    Validate whether the user input allows us to connect to the gateray.

    Data has the keys from _base_gw_schema() with values provided by the user.
    """
    websession = async_get_clientsession(hass, verify_ssl=False)

    api = Smile(
        host=data[CONF_HOST],
        password=data[CONF_PASSWORD],
        port=data[CONF_PORT],
        username=data[CONF_USERNAME],
        timeout=30,
        websession=websession,
    )

    try:
        await api.connect()
    except InvalidAuthentication as err:
        raise InvalidAuth from err
    except PlugwiseException as err:
        raise CannotConnect from err

    return api


# PLACEHOLDER USB connection validation


class PlugwiseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Plugwise Smile."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the Plugwise config flow."""
        self.discovery_info = {}

    async def async_step_zeroconf(self, discovery_info: DiscoveryInfoType):
        """Prepare configuration for a discovered Plugwise Smile."""
        self.discovery_info = discovery_info
        _properties = self.discovery_info.get("properties")

        unique_id = self.discovery_info.get("hostname").split(".")[0]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        _product = _properties.get("product", None)
        _version = _properties.get("version", "n/a")
        _name = f"{ZEROCONF_MAP.get(_product, _product)} v{_version}"

        # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167
        self.context["title_placeholders"] = {
            CONF_HOST: discovery_info[CONF_HOST],
            CONF_PORT: discovery_info.get(CONF_PORT, DEFAULT_PORT),
            CONF_NAME: _name,
        }
        return await self.async_step_user()

    async def async_step_user_gateway(self, user_input=None):
        """Handle the initial step for gateways."""
        errors = {}

        if user_input is not None:

            if self.discovery_info:
                user_input[CONF_HOST] = self.discovery_info[CONF_HOST]
                user_input[CONF_PORT] = self.discovery_info.get(CONF_PORT, DEFAULT_PORT)

            for entry in self._async_current_entries():
                if entry.data.get(CONF_HOST) == user_input[CONF_HOST]:
                    return self.async_abort(reason="already_configured")

            try:
                api = await validate_gw_input(self.hass, user_input)

            except CannotConnect:
                errors[CONF_BASE] = "cannot_connect"
            except InvalidAuth:
                errors[CONF_BASE] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors[CONF_BASE] = "unknown"
            if not errors:
                await self.async_set_unique_id(
                    api.smile_hostname or api.gateway_id, raise_on_progress=False
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(title=api.smile_name, data=user_input)

        return self.async_show_form(
            step_id="user_gateway",
            data_schema=_base_gw_schema(self.discovery_info),
            errors=errors or {},
        )

    async def async_step_user_usb(self, user_input=None):
        """Step when user initializes a integration."""
        errors = {}
        ports = await self.hass.async_add_executor_job(serial.tools.list_ports.comports)
        list_of_ports = [
            f"{p}, s/n: {p.serial_number or 'n/a'}"
            + (f" - {p.manufacturer}" if p.manufacturer else "")
            for p in ports
        ]
        list_of_ports.append(CONF_MANUAL_PATH)

        if user_input is not None:
            user_input.pop(FLOW_TYPE, None)
            user_selection = user_input[CONF_USB_PATH]
            if user_selection == CONF_MANUAL_PATH:
                return await self.async_step_manual_path()
            if user_selection in list_of_ports:
                port = ports[list_of_ports.index(user_selection)]
                device_path = await self.hass.async_add_executor_job(
                    get_serial_by_id, port.device
                )
            else:
                device_path = await self.hass.async_add_executor_job(
                    get_serial_by_id, user_selection
                )
            errors, stick = await validate_usb_connection(self.hass, device_path)
            if not errors:
                await self.async_set_unique_id(stick.get_mac_stick())
                return self.async_create_entry(
                    title="Stick", data={CONF_USB_PATH: device_path, PW_TYPE: STICK}
                )
        return self.async_show_form(
            step_id="user_usb",
            data_schema=vol.Schema(
                {vol.Required(CONF_USB_PATH): vol.In(list_of_ports)}
            ),
            errors=errors,
        )

    async def async_step_manual_path(self, user_input=None):
        """Step when manual path to device."""
        errors = {}
        if user_input is not None:
            user_input.pop(FLOW_TYPE, None)
            device_path = await self.hass.async_add_executor_job(
                get_serial_by_id, user_input.get(CONF_USB_PATH)
            )
            errors, stick = await validate_usb_connection(self.hass, device_path)
            if not errors:
                await self.async_set_unique_id(stick.get_mac_stick())
                return self.async_create_entry(
                    title="Stick", data={CONF_USB_PATH: device_path}
                )
        return self.async_show_form(
            step_id="manual_path",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USB_PATH, default="/dev/ttyUSB0" or vol.UNDEFINED
                    ): str
                }
            ),
            errors=errors,
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step when using network/gateway setups."""
        errors = {}
        if user_input is not None:
            if user_input[FLOW_TYPE] == FLOW_NET:
                return await self.async_step_user_gateway()

            if user_input[FLOW_TYPE] == FLOW_USB:
                return await self.async_step_user_usb()

        return self.async_show_form(
            step_id="user",
            data_schema=CONNECTION_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PlugwiseOptionsFlowHandler(config_entry)


class PlugwiseOptionsFlowHandler(config_entries.OptionsFlow):
    """Plugwise option flow."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Plugwise options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        api = self.hass.data[DOMAIN][self.config_entry.entry_id]["api"]
        interval = DEFAULT_SCAN_INTERVAL[api.smile_type]
        data = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL, interval),
            ): int
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(data))


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
