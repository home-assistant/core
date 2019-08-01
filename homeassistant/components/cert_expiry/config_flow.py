"""Config flow for the Cert Expiry platform."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT, CONF_NAME, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_NAME


@callback
def certexpiry_entries(hass: HomeAssistant):
    """Return the host,port tuples for the domain."""
    return set((entry.data[CONF_HOST], entry.data[CONF_PORT]) for
               entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class CertexpiryConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors = {}

    def _prt_in_configuration_exists(self, host: str, prt: int) -> bool:
        """Return True if host, port combination exists in configuration."""
        if (host, prt) in certexpiry_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Step when user intializes a integration."""
        self._errors = {}
        if user_input is not None:
            name = slugify(user_input[CONF_NAME])
            host = user_input[CONF_HOST]
            prt = user_input[CONF_PORT]
            if not self._prt_in_configuration_exists(host, prt):
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: prt
                    }
                )
            self._errors[CONF_HOST] = 'host_port_exists'
        else:
            user_input = {}
            user_input[CONF_NAME] = DEFAULT_NAME
            user_input[CONF_HOST] = ''
            user_input[CONF_PORT] = DEFAULT_PORT

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_NAME,
                             default=user_input[CONF_NAME]): str,
                vol.Required(CONF_HOST,
                             default=user_input[CONF_HOST]): str,
                vol.Required(CONF_PORT,
                             default=user_input[CONF_PORT]): int
            }),
            errors=self._errors
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry.

        Only host was required in the yaml file all other fields are optional
        """
        host = user_input[CONF_HOST]
        prt = user_input.get(CONF_PORT, DEFAULT_PORT)
        name = user_input.get(CONF_NAME, host)
        if self._prt_in_configuration_exists(host, prt):
            return self.async_abort(
                reason='host_port_exists'
                )
        return await self.async_step_user({
            CONF_NAME: name,
            CONF_HOST: host,
            CONF_PORT: prt
            })
