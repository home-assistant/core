"""Config flow for AV Receiver."""
from urllib.parse import urlparse

from pyavreceiver import factory
from pyavreceiver.error import AVReceiverIncompatibleDeviceError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST

from .const import DATA_DISCOVERED_HOSTS, DOMAIN


def format_title(host: str) -> str:
    """Format the title for config entries."""
    return f"AV Receiver ({host})"


@config_entries.HANDLERS.register(DOMAIN)
class AVReceiverFlowHandler(config_entries.ConfigFlow):
    """Define the config flow for AV Receiver."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Heos device."""
        # Store discovered host
        hostname = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname
        friendly_name = f"{discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]} ({hostname})"
        self.hass.data.setdefault(DATA_DISCOVERED_HOSTS, {})
        self.hass.data[DATA_DISCOVERED_HOSTS][friendly_name] = hostname
        # Abort if other flows in progress or an entry already exists
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        await self.async_set_unique_id(DOMAIN)
        # Show selection form
        return self.async_show_form(step_id="user")

    async def async_step_import(self, user_input=None):
        """Occurs when an entry is setup through config."""
        host = user_input[CONF_HOST]
        # raise_on_progress is False here in case ssdp discovers
        # first which would block the import
        await self.async_set_unique_id(DOMAIN, raise_on_progress=False)
        return self.async_create_entry(title=format_title(host), data={CONF_HOST: host})

    async def async_step_user(self, user_input=None):
        """Get host from user and check connection."""
        self.hass.data.setdefault(DATA_DISCOVERED_HOSTS, {})
        # Only a single entry is needed for all devices
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        # Try connecting to host
        errors = {}
        host = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                avreceiver = await factory(host)
                await avreceiver.init()
                await avreceiver.disconnect()
            except AVReceiverIncompatibleDeviceError:
                errors[CONF_HOST] = "cannot_connect"
            except AttributeError:
                pass
            return self.async_create_entry(
                title=format_title(host), data={CONF_HOST: host}
            )

        # Return user input form
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
