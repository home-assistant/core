"""Config flow to configure Heos."""
from urllib.parse import urlparse

from pyheos import Heos, HeosError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.ssdp import ATTR_NAME, ATTR_SSDP_LOCATION
from homeassistant.const import CONF_HOST

from .const import DATA_DISCOVERED_HOSTS, DOMAIN


def format_title(host: str) -> str:
    """Format the title for config entries."""
    return f"Controller ({host})"


@config_entries.HANDLERS.register(DOMAIN)
class HeosFlowHandler(config_entries.ConfigFlow):
    """Define a flow for HEOS."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Heos device."""
        # Store discovered host
        hostname = urlparse(discovery_info[ATTR_SSDP_LOCATION]).hostname
        friendly_name = "{} ({})".format(discovery_info[ATTR_NAME], hostname)
        self.hass.data.setdefault(DATA_DISCOVERED_HOSTS, {})
        self.hass.data[DATA_DISCOVERED_HOSTS][friendly_name] = hostname
        # Abort if other flows in progress or an entry already exists
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="already_setup")
        # Show selection form
        return self.async_show_form(step_id="user")

    async def async_step_import(self, user_input=None):
        """Occurs when an entry is setup through config."""
        host = user_input[CONF_HOST]
        return self.async_create_entry(title=format_title(host), data={CONF_HOST: host})

    async def async_step_user(self, user_input=None):
        """Obtain host and validate connection."""
        self.hass.data.setdefault(DATA_DISCOVERED_HOSTS, {})
        # Only a single entry is needed for all devices
        if self._async_current_entries():
            return self.async_abort(reason="already_setup")
        # Try connecting to host if provided
        errors = {}
        host = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            # Map host from friendly name if in discovered hosts
            host = self.hass.data[DATA_DISCOVERED_HOSTS].get(host, host)
            heos = Heos(host)
            try:
                await heos.connect()
                self.hass.data.pop(DATA_DISCOVERED_HOSTS)
                return await self.async_step_import({CONF_HOST: host})
            except HeosError:
                errors[CONF_HOST] = "connection_failure"
            finally:
                await heos.disconnect()

        # Return form
        host_type = (
            str
            if not self.hass.data[DATA_DISCOVERED_HOSTS]
            else vol.In(list(self.hass.data[DATA_DISCOVERED_HOSTS]))
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST, default=host): host_type}),
            errors=errors,
        )
