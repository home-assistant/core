"""Config flow for the Cert Expiry platform."""
import socket
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT, CONF_NAME, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_NAME
from .helper import get_cert


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
        """Test connection to the server and try to get the certtificate."""
        try:
            await self.hass.async_add_executor_job(
                get_cert, user_input[CONF_HOST], user_input.get(CONF_PORT, DEFAULT_PORT)
            )
            return True
        except socket.gaierror:
            self._errors[CONF_HOST] = "resolve_failed"
        except socket.timeout:
            self._errors[CONF_HOST] = "connection_timeout"
        except OSError:
            self._errors[CONF_HOST] = "certificate_fetch_failed"
        return False

    async def async_step_user(self, user_input=None):
        """Step when user intializes a integration."""
        self._errors = {}
        if user_input is not None:
            # set some defaults in case we need to return to the form
            if self._prt_in_configuration_exists(user_input):
                self._errors[CONF_HOST] = "host_port_exists"
            else:
                if await self._test_connection(user_input):
                    host = user_input[CONF_HOST]
                    name = slugify(user_input.get(CONF_NAME, DEFAULT_NAME))
                    prt = user_input.get(CONF_PORT, DEFAULT_PORT)
                    return self.async_create_entry(
                        title=name, data={CONF_HOST: host, CONF_PORT: prt}
                    )
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_HOST] = ""
            user_input[CONF_PORT] = DEFAULT_PORT

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)
                    ): str,
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
