"""Adds config flow for Dune HD integration."""
import ipaddress
import logging
import re

from pdunehd import DuneHDPlayer
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version in [4, 6]:
            return True
    except ValueError:
        if len(host) > 253:
            return False
        allowed = re.compile(r"(?!-)[A-Z\d\-\_]{1,63}(?<!-)$", re.IGNORECASE)
        return all(allowed.match(x) for x in host.split("."))


class DuneHDConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dune HD integration."""

    VERSION = 1

    def __init__(self):
        """Initialize."""
        self.host = None

    async def init_device(self, host):
        """Initialize Dune HD player."""
        player = DuneHDPlayer(host)
        state = await self.hass.async_add_executor_job(player.update_state)
        if not state:
            raise CannotConnect()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if host_valid(user_input[CONF_HOST]):
                self.host = user_input[CONF_HOST]

                try:
                    if self.host_already_configured(self.host):
                        raise AlreadyConfigured()
                    await self.init_device(self.host)
                except CannotConnect:
                    errors[CONF_HOST] = "cannot_connect"
                except AlreadyConfigured:
                    errors[CONF_HOST] = "already_configured"
                else:
                    return self.async_create_entry(title=self.host, data=user_input)
            else:
                errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=""): str}),
            errors=errors,
        )

    async def async_step_import(self, user_input=None):
        """Handle configuration by yaml file."""
        self.host = user_input[CONF_HOST]

        if self.host_already_configured(self.host):
            return self.async_abort(reason="already_configured")

        try:
            await self.init_device(self.host)
        except CannotConnect:
            _LOGGER.error("Import aborted, cannot connect to %s", self.host)
            return self.async_abort(reason="cannot_connect")
        else:
            return self.async_create_entry(title=self.host, data=user_input)

    def host_already_configured(self, host):
        """See if we already have a dunehd entry matching user input configured."""
        existing_hosts = {
            entry.data[CONF_HOST] for entry in self._async_current_entries()
        }
        return host in existing_hosts


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate device is already configured."""
