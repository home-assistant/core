"""Config flow for ScreenLogic."""
import socket

from screenlogicpy import discover, ScreenLogicGateway, ScreenLogicError

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv

from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_NAME,
)

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Optional(CONF_PORT, default=80): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)
        ),
    }
)


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""

    def discover_screenlogic():
        try:
            host = discover()
            _LOGGER.debug(host)
            return host
        except ScreenLogicError as error:
            _LOGGER.debug(error)
            return None

    _LOGGER.debug("Attempting to discover ScreenLogic devices")
    return await hass.async_add_executor_job(discover_screenlogic)


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

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        _LOGGER.debug("async_step_user: user_input")
        _LOGGER.debug(user_input)

        # First, attempt to discover a ScreenLogic Gateway
        if not user_input:
            _LOGGER.debug("No input: Discover")
            host = await _async_has_devices(self.hass)
            if host:
                _LOGGER.debug("Found ScreenLogic Device!")
                _LOGGER.debug(host)
                user_input = {
                    CONF_IP_ADDRESS: host["ip"],
                    CONF_PORT: host["port"],
                    CONF_NAME: host["name"],
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                }
                _LOGGER.debug(user_input)

        def validate_user_input():
            errors = {}
            if CONF_IP_ADDRESS not in user_input:
                errors[CONF_IP_ADDRESS] = "ip_missing"
            if CONF_PORT not in user_input:
                errors[CONF_PORT] = "port_missing"
            if CONF_SCAN_INTERVAL not in user_input:
                errors[CONF_SCAN_INTERVAL] = "interval_missing"
            elif user_input[CONF_SCAN_INTERVAL] < MIN_SCAN_INTERVAL:
                errors[CONF_SCAN_INTERVAL] = "interval_low"
            if errors:
                return errors
            try:
                gateway = ScreenLogicGateway(
                    user_input[CONF_IP_ADDRESS], user_input[CONF_PORT]
                )
                if CONF_NAME not in user_input:
                    user_input[CONF_NAME] = socket.gethostbyaddr(
                        user_input[CONF_IP_ADDRESS]
                    )[0].split(".")[0]
            except ScreenLogicError:
                errors[CONF_IP_ADDRESS] = "can_not_connect"
            except socket.herror:
                user_input[CONF_NAME] = user_input[CONF_IP_ADDRESS]
            return errors

        entry_errors = {}
        if user_input:
            entry_errors = await self.hass.async_add_executor_job(validate_user_input)

            if CONF_NAME in user_input and user_input[CONF_NAME]:
                device_unique_id = user_input[CONF_NAME]
            else:
                device_unique_id = user_input[CONF_IP_ADDRESS]

            if device_unique_id in configured_instances(self.hass):
                entry_errors[CONF_IP_ADDRESS] = "already_configured"

        if not user_input or entry_errors:
            _LOGGER.debug("Show Form, errors:")
            _LOGGER.debug(entry_errors)
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors=entry_errors,
                description_placeholders={},
            )

        if device_unique_id:
            await self.async_set_unique_id(device_unique_id)
        # await self._async_handle_discovery_without_unique_id()
        _LOGGER.debug("Create Config Entry")
        return self.async_create_entry(title=device_unique_id, data=user_input)
