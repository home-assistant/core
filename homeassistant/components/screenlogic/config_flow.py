"""Config flow for ScreenLogic."""
import logging

from screenlogicpy import ScreenLogicError, discover
from screenlogicpy.const import SL_GATEWAY_IP, SL_GATEWAY_NAME, SL_GATEWAY_PORT
from screenlogicpy.requests import login
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

GATEWAY_SELECT_KEY = "selected_gateway"
GATEWAY_MANUAL_ENTRY = "manual"

GATEWAY_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_PORT, default=80): int,
    }
)


def discover_gateways():
    """Discover screen logic gateways."""
    _LOGGER.debug("Attempting to discover ScreenLogic devices")
    try:
        return discover()
    except ScreenLogicError as ex:
        _LOGGER.debug(ex)
        return None


def _extract_unique_id_from_name(name):
    return name.split(":")[1].strip()


async def async_discover_gateways_by_unique_id(hass):
    """Discover gateways and return a dict of them by unique id."""
    discovered_gateways = {}
    hosts = await hass.async_add_executor_job(discover_gateways)
    if not hosts:
        return discovered_gateways

    for host in hosts:
        discovered_gateways[_extract_unique_id_from_name(host[SL_GATEWAY_NAME])] = host

    return discovered_gateways


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    hosts = await hass.async_add_executor_job(discover_gateways)
    return len(hosts) > 0


_LOGGER.info("Registering discovery flow")
config_entry_flow.register_discovery_flow(
    DOMAIN,
    "Pentair ScreenLogic",
    _async_has_devices,
    config_entries.CONN_CLASS_LOCAL_POLL,
)


def configured_instances(hass):
    """Return a set of configured Screenlogic instances."""
    return {
        entry.unique_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.unique_id is not None
    }


async def async_get_mac_address(hass, ip_address, port):
    """Connect to a screenlogic gateway and return the mac address."""
    connected_socket = await hass.async_add_executor_job(
        login.create_socket,
        ip_address,
        port,
    )
    if not connected_socket:
        raise ScreenLogicError("Unknown socket error")
    return await hass.async_add_executor_job(login.gateway_connect, connected_socket)


class ScreenlogicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow to setup screen logic devices."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize ScreenLogic ConfigFlow."""
        self.discovered_gateways = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for ScreenLogic."""
        return ScreenLogicOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        _LOGGER.debug("async_step_user: user_input")
        _LOGGER.debug(user_input)
        self.discovered_gateways = await async_discover_gateways_by_unique_id(self.hass)
        return await self.async_step_gateway_entry()

    async def async_step_gateway_select(self, user_input=None):
        """Handle the selection of a discovered ScreenLogic gateway."""
        _LOGGER.debug("Gateway Select")
        _LOGGER.debug(
            *[gateway[SL_GATEWAY_NAME] for gateway in self.discovered_gateways.values()]
        )
        existing = configured_instances(self.hass)
        unconfigured_gateways = {
            unique_id: gateway[SL_GATEWAY_NAME]
            for unique_id, gateway in self.discovered_gateways.items()
            if unique_id not in existing
        }

        errors = {}
        if user_input is not None:
            if user_input[GATEWAY_SELECT_KEY] == GATEWAY_MANUAL_ENTRY:
                return await self.async_step_gateway_entry()

            unique_id = user_input[GATEWAY_SELECT_KEY]
            selected_gateway = self.discovered_gateways[unique_id]
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Pentair: {unique_id}",
                data={
                    CONF_IP_ADDRESS: selected_gateway[SL_GATEWAY_IP],
                    CONF_PORT: selected_gateway[SL_GATEWAY_PORT],
                },
            )

        return self.async_show_form(
            step_id="gateway_select",
            data_schema=vol.Schema(
                {
                    vol.Required(GATEWAY_SELECT_KEY): vol.In(
                        {
                            **unconfigured_gateways,
                            GATEWAY_MANUAL_ENTRY: "Manually configure a ScreenLogic gateway",
                        }
                    )
                }
            ),
            errors=errors,
            description_placeholders={},
        )

    async def async_step_gateway_entry(self, user_input=None):
        """Handle the manual entry of a ScreenLogic gateway."""
        _LOGGER.debug("Gateway Entry")
        errors = {}
        if user_input is not None:
            try:
                mac = await async_get_mac_address(
                    self.hass, user_input[CONF_IP_ADDRESS], user_input[CONF_PORT]
                )
            except ScreenLogicError:
                errors[CONF_IP_ADDRESS] = "can_not_connect"

            if not errors:
                unique_id = _format_mac_to_unique_id(mac)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Pentair: {unique_id}",
                    data={
                        CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                )

        return self.async_show_form(
            step_id="gateway_entry",
            data_schema=GATEWAY_ENTRY_SCHEMA,
            errors=errors,
            description_placeholders={},
        )


def _format_mac_to_unique_id(mac):
    return "-".join(mac.split("-"))[3:]


class ScreenLogicOptionsFlowHandler(config_entries.OptionsFlow):
    """Handles the options for the ScreenLogic integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Init the screen logic options flow."""
        _LOGGER.debug(config_entry)
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug("Options user_input:")
            _LOGGER.debug(user_input)
            return self.async_create_entry(
                title=self.config_entry.title, data=user_input
            )

        current_interval = DEFAULT_SCAN_INTERVAL

        # TODO: migrate the entry data to options flow when the integration is
        # setup.  There is an example in homekit
        if CONF_SCAN_INTERVAL in self.config_entry.options:
            current_interval = self.config_entry.options[CONF_SCAN_INTERVAL]
        elif CONF_SCAN_INTERVAL in self.config_entry.data:
            current_interval = self.config_entry.data[CONF_SCAN_INTERVAL]

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL))
                }
            ),
            description_placeholders={"gateway_name": self.config_entry.title},
        )
