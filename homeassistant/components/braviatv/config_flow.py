"""Adds config flow for Bravia TV integration."""
import ipaddress
import logging
import re

from bravia_tv import BraviaRC
from bravia_tv.braviarc import NoIPControl
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_CID,
    ATTR_MAC,
    ATTR_MODEL,
    BRAVIARC,
    CLIENTID_PREFIX,
    CONF_IGNORED_SOURCES,
    DOMAIN,
    NICKNAME,
)

_LOGGER = logging.getLogger(__name__)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version in [4, 6]:
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


class BraviaTVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BraviaTV integration."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.braviarc = None
        self.host = None
        self.title = None
        self.mac = None

    async def init_device(self, pin):
        """Initialize Bravia TV device."""
        await self.hass.async_add_executor_job(
            self.braviarc.connect, pin, CLIENTID_PREFIX, NICKNAME
        )

        connected = await self.hass.async_add_executor_job(self.braviarc.is_connected)
        if not connected:
            raise CannotConnect()

        system_info = await self.hass.async_add_executor_job(
            self.braviarc.get_system_info
        )
        if not system_info:
            raise ModelNotSupported()

        await self.async_set_unique_id(system_info[ATTR_CID].lower())
        self._abort_if_unique_id_configured()

        self.title = system_info[ATTR_MODEL]
        self.mac = system_info[ATTR_MAC]

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Bravia TV options callback."""
        return BraviaTVOptionsFlowHandler(config_entry)

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        self.host = user_input[CONF_HOST]
        self.braviarc = BraviaRC(self.host)

        try:
            await self.init_device(user_input[CONF_PIN])
        except CannotConnect:
            _LOGGER.error("Import aborted, cannot connect to %s", self.host)
            return self.async_abort(reason="cannot_connect")
        except NoIPControl:
            _LOGGER.error("IP Control is disabled in the TV settings")
            return self.async_abort(reason="no_ip_control")
        except ModelNotSupported:
            _LOGGER.error("Import aborted, your TV is not supported")
            return self.async_abort(reason="unsupported_model")

        user_input[CONF_MAC] = self.mac

        return self.async_create_entry(title=self.title, data=user_input)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if host_valid(user_input[CONF_HOST]):
                self.host = user_input[CONF_HOST]
                self.braviarc = BraviaRC(self.host)

                return await self.async_step_authorize()

            errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_authorize(self, user_input=None):
        """Get PIN from the Bravia TV device."""
        errors = {}

        if user_input is not None:
            try:
                await self.init_device(user_input[CONF_PIN])
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except ModelNotSupported:
                errors["base"] = "unsupported_model"
            else:
                user_input[CONF_HOST] = self.host
                user_input[CONF_MAC] = self.mac
                return self.async_create_entry(title=self.title, data=user_input)

        # Connecting with th PIN "0000" to start the pairing process on the TV.
        try:
            await self.hass.async_add_executor_job(
                self.braviarc.connect, "0000", CLIENTID_PREFIX, NICKNAME
            )
        except NoIPControl:
            return self.async_abort(reason="no_ip_control")

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema({vol.Required(CONF_PIN, default=""): str}),
            errors=errors,
        )


class BraviaTVOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options for Bravia TV."""

    def __init__(self, config_entry):
        """Initialize Bravia TV options flow."""
        self.braviarc = None
        self.config_entry = config_entry
        self.pin = config_entry.data[CONF_PIN]
        self.ignored_sources = config_entry.options.get(CONF_IGNORED_SOURCES)
        self.source_list = []

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        self.braviarc = self.hass.data[DOMAIN][self.config_entry.entry_id][BRAVIARC]
        connected = await self.hass.async_add_executor_job(self.braviarc.is_connected)
        if not connected:
            await self.hass.async_add_executor_job(
                self.braviarc.connect, self.pin, CLIENTID_PREFIX, NICKNAME
            )

        content_mapping = await self.hass.async_add_executor_job(
            self.braviarc.load_source_list
        )
        self.source_list = [*content_mapping]
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_IGNORED_SOURCES, default=self.ignored_sources
                    ): cv.multi_select(self.source_list)
                }
            ),
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class ModelNotSupported(exceptions.HomeAssistantError):
    """Error to indicate not supported model."""
