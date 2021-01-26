"""Config Flow For Ebus Integration."""
import ipaddress
import logging
import re

from pyebus import CommandError, Ebus
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (  # pylint: disable=unused-import
    CONF_CIRCUITINFOS,
    CONF_MSGDEFCODES,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


class EbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow For Ebus Integration."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self.host = DEFAULT_HOST
        self.port = DEFAULT_PORT
        self.ebus = None

    async def async_step_user(self, user_input=None):
        """Handle The User Step."""
        errors = {}

        if user_input is not None:
            if host_valid(user_input[CONF_HOST]):
                self.host = user_input[CONF_HOST]
                self.port = user_input[CONF_PORT]
                self.ebus = Ebus(self.host, self.port, timeout=TIMEOUT)
                try:
                    is_online = await self.ebus.async_is_online()
                    await self.ebus.async_wait_scancompleted()
                    await self.ebus.async_load_msgdefs()
                    await self.ebus.async_load_circuitinfos()
                    if is_online:
                        await self.async_set_unique_id(
                            f"{self.ebus.host}:{self.ebus.port}"
                        )
                        self._abort_if_unique_id_configured()
                    else:
                        errors[CONF_HOST] = "ebus_error"
                except (ConnectionError, ConnectionRefusedError, CommandError):
                    errors[CONF_HOST] = "connection_error"
                else:
                    # Create Configuration Entry
                    title = f"EBUS {self.host}:{self.port}"
                    data = {
                        CONF_HOST: self.host,
                        CONF_PORT: self.port,
                        CONF_MSGDEFCODES: self.ebus.msgdefcodes,
                        CONF_CIRCUITINFOS: [
                            circuitinfo._asdict()
                            for circuitinfo in self.ebus.circuitinfos
                        ],
                    }
                    return self.async_create_entry(title=title, data=data)
            else:
                errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.host): str,
                    vol.Required(CONF_PORT, default=self.port): str,
                }
            ),
            errors=errors,
        )
