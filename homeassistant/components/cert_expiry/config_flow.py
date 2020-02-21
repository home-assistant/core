"""Config flow for the Cert Expiry platform."""
import logging
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback

from .const import DEFAULT_PORT, DOMAIN
from .errors import TemporaryFailure, ValidationFailure
from .helper import get_cert_time_to_expiry

_LOGGER = logging.getLogger(__name__)


@callback
def certexpiry_entries(hass: HomeAssistant):
    """Return the host,port tuples for the domain."""
    return set(
        (entry.data[CONF_HOST], entry.data[CONF_PORT])
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


class CertexpiryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors = {}

    def _prt_in_configuration_exists(self, user_input) -> bool:
        """Return True if host, port combination exists in configuration."""
        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT, DEFAULT_PORT)
        if (host, port) in certexpiry_entries(self.hass):
            return True
        return False

    async def _test_connection(self, user_input=None):
        """Test connection to the server and try to get the certificate."""
        try:
            await get_cert_time_to_expiry(
                self.hass,
                user_input[CONF_HOST],
                user_input.get(CONF_PORT, DEFAULT_PORT),
            )
            return True
        except TemporaryFailure as err:
            cause = type(err.__cause__)
            if cause is socket.gaierror:
                self._errors[CONF_HOST] = "resolve_failed"
            elif cause is socket.timeout:
                self._errors[CONF_HOST] = "connection_timeout"
            elif cause is ConnectionRefusedError:
                self._errors[CONF_HOST] = "connection_refused"
        except ValidationFailure:
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        self._errors = {}
        if user_input is not None:
            if self._prt_in_configuration_exists(user_input):
                return self.async_abort(reason="host_port_exists")

            if await self._test_connection(user_input):
                host = user_input[CONF_HOST]
                port = user_input.get(CONF_PORT, DEFAULT_PORT)
                title = host + (f":{port}" if port != DEFAULT_PORT else "")
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input.get(CONF_PORT, DEFAULT_PORT),
                    },
                )
            if (  # pylint: disable=no-member
                self.context["source"] == config_entries.SOURCE_IMPORT
            ):
                _LOGGER.error("Config import failed for %s", user_input[CONF_HOST])
                return self.async_abort(reason="import_failed")
        else:
            user_input = {}
            user_input[CONF_HOST] = ""
            user_input[CONF_PORT] = DEFAULT_PORT

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(
                        CONF_PORT, default=user_input.get(CONF_PORT, DEFAULT_PORT)
                    ): int,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry.

        Only host was required in the yaml file all other fields are optional
        """
        if self._prt_in_configuration_exists(user_input):
            return self.async_abort(reason="host_port_exists")
        return await self.async_step_user(user_input)
