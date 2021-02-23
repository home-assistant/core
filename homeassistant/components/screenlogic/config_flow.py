"""Config flow for ScreenLogic."""
import socket

from screenlogicpy import discover, ScreenLogicGateway, ScreenLogicError
from screenlogicpy.requests import login
from screenlogicpy.const import (
    SL_GATEWAY_IP,
    SL_GATEWAY_PORT,
    SL_GATEWAY_TYPE,
    SL_GATEWAY_SUBTYPE,
    SL_GATEWAY_NAME,
)

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback

from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_NAME,
    CONF_HOST,
    CONF_DISCOVERY,
    CONF_MAC,
)

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

GATEWAY_SELECT_KEY = "selected_gateway"
MANUAL_ENTRY = "Manually Enter"


def discover_gateways():
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
    return {entry.unique_id for entry in hass.config_entries.async_entries(DOMAIN)}


class ScreenlogicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize ScreenLogic ConfigFlow."""
        self.gateways = {}

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
            hosts.append(
                {
                    SL_GATEWAY_IP: "192.168.1.43",
                    SL_GATEWAY_PORT: 80,
                    SL_GATEWAY_TYPE: 2,
                    SL_GATEWAY_SUBTYPE: 12,
                    SL_GATEWAY_NAME: "Test Gateway",
                }
            )
            if len(hosts) > 0:
                for host in hosts:
                    self.gateways[host[SL_GATEWAY_NAME]] = host
                return await self.async_step_gateway_select()
            else:
                return await self.async_step_gateway_entry()

    async def async_step_gateway_select(self, user_input=None):
        """Handle the selection of a discovered ScreenLogic gateway."""

        _LOGGER.debug("Gateway Select")

        OPTIONS = [key for key in self.gateways.keys()]
        OPTIONS.append(MANUAL_ENTRY)
        _LOGGER.debug(OPTIONS)

        GATEWAY_SELECT_SCHEMA = vol.Schema(
            {vol.Required(GATEWAY_SELECT_KEY, default=OPTIONS[0]): vol.In(OPTIONS)}
        )

        entry_errors = {}
        if user_input is not None:
            # TODO: create user_input
            if user_input[GATEWAY_SELECT_KEY] == MANUAL_ENTRY:
                return await self.async_step_gateway_entry()

            selected_gateway = self.gateways[user_input[GATEWAY_SELECT_KEY]]
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
                connected_socket = login.create_socket(
                    user_input[CONF_IP_ADDRESS],
                    user_input[CONF_PORT],
                )
                if not connected_socket:
                    raise ScreenLogicError("Unknown socket error")
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
    """Handles the options for the ScreenLogic integration"""

    def __init__(self, config_entry: config_entries.ConfigEntry):
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
