"""Config Flow For Ebus Integration."""
import ipaddress
import logging
import re

from pyebus import NA, Ebus
from pyebus.connection import ConnectionTimeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_MESSAGES,
    CONF_MSGDEFCODES,
    DEFAULT_HOST,
    DEFAULT_MESSAGES,
    DEFAULT_PORT,
    DOMAIN,
    PRIO,
    TTL,
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
        self.messages = DEFAULT_MESSAGES
        self.ebus = None

    async def async_step_user(self, user_input=None):
        """Handle The User Step."""
        errors = {}

        if user_input is not None:
            if host_valid(user_input[CONF_HOST]):
                self.host = user_input[CONF_HOST]
                self.port = user_input[CONF_PORT]
                self.messages = user_input[CONF_MESSAGES]
                self.ebus = Ebus(self.host, self.port, timeout=3)
                try:
                    is_online = await self.ebus.is_online()
                    await self.ebus.wait_scancompleted()
                    if is_online:
                        await self.async_set_unique_id(
                            f"{self.ebus.host}:{self.ebus.port}"
                        )
                        self._abort_if_unique_id_configured()
                    else:
                        errors[CONF_HOST] = "ebus_error"
                except ConnectionTimeout:
                    errors[CONF_HOST] = "connection_error"
                except ConnectionRefusedError:
                    errors[CONF_HOST] = "connection_error"
                except Exception as exc:
                    _LOGGER.error(exc)
                    errors[CONF_HOST] = "invalid_host"
                else:
                    return self.async_show_form(
                        step_id="wait", data_schema=vol.Schema({})
                    )
            else:
                errors[CONF_HOST] = "invalid_host"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.host): str,
                    vol.Required(CONF_PORT, default=self.port): str,
                    vol.Optional(CONF_MESSAGES, default=self.messages): str,
                }
            ),
            errors=errors,
        )

    async def async_step_wait(self, user_input=None):
        """Handle The User Step."""
        ebus = self.ebus
        if user_input is not None:
            messages = []

            await ebus.load_msgdefs()
            if self.messages:
                ebus.msgdefs = ebus.msgdefs.resolve(self.messages.split(";"))
            for msgdef in ebus.msgdefs:
                # only list readable messages
                if msgdef.read:
                    msg = await ebus.read(
                        msgdef, defaultprio=PRIO, setprio=True, ttl=TTL
                    )
                    if msg.valid:
                        if all(field.value != NA for field in msg.fields):
                            messages.append(msgdef.ident)
                            _LOGGER.info(f"Message found: {msgdef.ident}")
                        else:
                            for field in msg.fields:
                                if field.value != NA:
                                    _LOGGER.info(f"Field found: {field.fielddef.ident}")
                                    messages.append(field.fielddef.ident)

                                else:
                                    _LOGGER.warn(
                                        f"Field broken: {field.fielddef.ident}"
                                    )
                    else:
                        _LOGGER.warn(f"Message broken: {msgdef.ident}")
                else:
                    messages.append(msgdef.ident)
                    _LOGGER.info(f"Message found: {msgdef.ident}")
            # Create Configuration Entry
            title = f"{self.host}:{self.port}"
            data = {
                CONF_HOST: self.host,
                CONF_PORT: self.port,
                CONF_MESSAGES: messages,
                CONF_MSGDEFCODES: self.ebus.msgdefcodes,
            }
            return self.async_create_entry(title=title, data=data)
        return self.async_show_form(step_id="wait", data_schema=vol.Schema({}))
