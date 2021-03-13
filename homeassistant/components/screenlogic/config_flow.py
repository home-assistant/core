"""Config flow for ScreenLogic."""
import logging

from screenlogicpy import ScreenLogicError, discover
from screenlogicpy.const import SL_GATEWAY_IP, SL_GATEWAY_NAME, SL_GATEWAY_PORT
from screenlogicpy.requests import login
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import callback
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

GATEWAY_SELECT_KEY = "selected_gateway"
GATEWAY_MANUAL_ENTRY = "manual"


def discover_gateways():
    """Discover screen logic gateways."""
    _LOGGER.debug("Attempting to discover ScreenLogic devices")
    try:
        hosts = discover()
        return hosts
    except ScreenLogicError as ex:
        _LOGGER.debug(ex)
        return None


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
    # entries that have been ignored will not have a unique_id
    return {entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN)}


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

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_gateway_entry(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        _LOGGER.debug("async_step_user: user_input")
        _LOGGER.debug(user_input)

        # First, attempt to discover a ScreenLogic Gateway
        if not user_input:
            _LOGGER.debug("No input: Discover")
            hosts = []
            hosts = await self.hass.async_add_executor_job(discover_gateways)
            if len(hosts) > 0:
                for host in hosts:
                    self.discovered_gateways[host[SL_GATEWAY_IP]] = host
                return await self.async_step_gateway_select()

            return await self.async_step_gateway_entry()

    async def async_step_gateway_select(self, user_input=None):
        """Handle the selection of a discovered ScreenLogic gateway."""
        _LOGGER.debug("Gateway Select")
        _LOGGER.debug(
            *[gateway[SL_GATEWAY_NAME] for gateway in self.discovered_gateways.values()]
        )

        # TODO: exclude already configured gateways that have a config entry per configured_instances
        GATEWAY_SELECT_SCHEMA = vol.Schema(
            {
                vol.Required(GATEWAY_SELECT_KEY): vol.In(
                    {
                        **{
                            gateway_ip: gateway[SL_GATEWAY_NAME]
                            for gateway_ip, gateway in self.discovered_gateways.items()
                        },
                        GATEWAY_MANUAL_ENTRY: "Manually configure a ScreenLogic gateway",
                    }
                )
            }
        )

        entry_errors = {}
        if user_input is not None:
            # TODO: create user_input
            if user_input[GATEWAY_SELECT_KEY] == GATEWAY_MANUAL_ENTRY:
                return await self.async_step_gateway_entry()

            selected_gateway = self.discovered_gateways[user_input[GATEWAY_SELECT_KEY]]
            entry_data = {
                CONF_HOST: {
                    CONF_IP_ADDRESS: selected_gateway[SL_GATEWAY_IP],
                    CONF_PORT: selected_gateway[SL_GATEWAY_PORT],
                    CONF_NAME: selected_gateway[SL_GATEWAY_NAME],
                },
            }

            await self.async_set_unique_id(entry_data[CONF_HOST][CONF_IP_ADDRESS])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=entry_data[CONF_HOST][CONF_NAME], data=entry_data
            )

        return self.async_show_form(
            step_id="gateway_select",
            data_schema=GATEWAY_SELECT_SCHEMA,
            errors=entry_errors,
            description_placeholders={},
        )

    async def async_step_gateway_entry(self, user_input=None):
        """Handle the manual entry of a ScreenLogic gateway."""
        _LOGGER.debug("Gateway Entry")

        GATEWAY_ENTRY_SCHEMA = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Optional(CONF_PORT, default=80): int,
            }
        )

        _LOGGER.debug("Gateway Entry post-schema")

        def validate_user_input():
            errors = {}
            if CONF_IP_ADDRESS not in user_input:
                errors[CONF_IP_ADDRESS] = "ip_missing"
            if CONF_PORT not in user_input:
                errors[CONF_PORT] = "port_missing"
            if errors:
                return errors
            if user_input[CONF_IP_ADDRESS] in configured_instances(self.hass):
                errors[CONF_IP_ADDRESS] = "already_configured"
                return errors
            try:
                # TODO: run in executor w/async_add_executor_job since this is doing I/O
                connected_socket = login.create_socket(
                    user_input[CONF_IP_ADDRESS],
                    user_input[CONF_PORT],
                )
                if not connected_socket:
                    raise ScreenLogicError("Unknown socket error")
                # TODO: run in executor w/async_add_executor_job since this is doing I/O
                mac = login.gateway_connect(connected_socket)
                if CONF_NAME not in user_input:
                    derived_name = "Pentair: " + "-".join(mac.split("-")[3:])
                    user_input[CONF_NAME] = derived_name
            except ScreenLogicError:
                errors[CONF_IP_ADDRESS] = "can_not_connect"
            return errors

        entry_errors = {}
        if user_input is not None:
            entry_errors = validate_user_input()
            if not entry_errors:
                entry_data = {
                    CONF_HOST: {
                        CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                        CONF_PORT: user_input[CONF_PORT],
                        CONF_NAME: user_input[CONF_NAME],
                    },
                }
                # TODO: use mac instead of ip address
                # https://developers.home-assistant.io/docs/config_entries_config_flow_handler/#unique-id-requirements
                await self.async_set_unique_id(entry_data[CONF_HOST][CONF_IP_ADDRESS])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=entry_data[CONF_HOST][CONF_NAME], data=entry_data
                )

        return self.async_show_form(
            step_id="gateway_entry",
            data_schema=GATEWAY_ENTRY_SCHEMA,
            errors=entry_errors,
            description_placeholders={},
        )


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
