"""Config flow for AV Receiver."""
from urllib.parse import urlparse

from pyavreceiver import factory
from pyavreceiver.error import AVReceiverIncompatibleDeviceError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import CONF_HOST, CONF_ID
from homeassistant.core import callback

from .const import (
    CONF_ZONE2,
    CONF_ZONE3,
    CONF_ZONE4,
    DATA_DISCOVERED_HOSTS,
    DEFAULT_ZONE_DISABLED,
    DOMAIN,
)


def format_title(host: str) -> str:
    """Format the title for config entries."""
    return f"AV Receiver ({host})"


@config_entries.HANDLERS.register(DOMAIN)
class AVReceiverFlowHandler(config_entries.ConfigFlow):
    """Define the config flow for AV Receiver."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "OptionsFlowHandler":
        """Get the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_ssdp(self, discovery_info):
        """Handle a discovered Heos device."""
        # Store discovered host
        hostname = urlparse(discovery_info[ssdp.ATTR_SSDP_LOCATION]).hostname
        friendly_name = f"{discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME]} ({hostname})"
        serial = discovery_info[ssdp.ATTR_UPNP_SERIAL]
        self.hass.data.setdefault(DATA_DISCOVERED_HOSTS, {})
        self.hass.data[DATA_DISCOVERED_HOSTS][friendly_name] = hostname
        # Abort if other flows in progress or an entry already exists
        if self._async_in_progress() or self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        await self.async_set_unique_id(f"{DOMAIN}-{serial}")
        # Show selection form
        return self.async_show_form(step_id="user")

    async def async_step_user(self, user_input=None):
        """Get host from user and check connection."""
        self.hass.data.setdefault(DATA_DISCOVERED_HOSTS, {})
        # Try connecting to host
        errors = {}
        host = None
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                avreceiver = await factory(host)
                await avreceiver.init()
                await avreceiver.disconnect()
                self.hass.data.pop(DATA_DISCOVERED_HOSTS)
                unique_id = (
                    f"{DOMAIN}-{avreceiver.serial_number or avreceiver.mac or host}"
                )
                await self.async_set_unique_id(unique_id, raise_on_progress=False)
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.data[CONF_HOST] == host:
                        return self.async_abort(reason="single_instance_allowed")
                return self.async_create_entry(
                    title=format_title(host), data={CONF_HOST: host, CONF_ID: unique_id}
                )
            except AVReceiverIncompatibleDeviceError:
                errors[CONF_HOST] = "cannot_connect"

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


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options for AV Receivers."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Init AV Receiver options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the AV Receiver options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_ZONE2,
                default=self.config_entry.options.get(
                    CONF_ZONE2, DEFAULT_ZONE_DISABLED
                ),
            ): bool,
            vol.Optional(
                CONF_ZONE3,
                default=self.config_entry.options.get(
                    CONF_ZONE3, DEFAULT_ZONE_DISABLED
                ),
            ): bool,
            vol.Optional(
                CONF_ZONE4,
                default=self.config_entry.options.get(
                    CONF_ZONE4, DEFAULT_ZONE_DISABLED
                ),
            ): bool,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
