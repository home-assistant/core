"""Config flow for openhome."""


from homeassistant.components.ssdp import (
    ATTR_SSDP_LOCATION,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DOMAIN_DATA_ENTRIES


def get_entry_device(hass, entry):
    """Retrieve device associated with a config entry."""
    return hass.data[DOMAIN_DATA_ENTRIES][entry.entry_id]


class OpenhomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Openhome config flow."""

    def __init__(self):
        """Set up the instance."""
        self.discovery_info = {}

    async def async_step_ssdp(self, discovery_info: dict) -> FlowResult:
        """Handle a flow initialized by discovery."""

        udn = discovery_info[ATTR_UPNP_UDN]
        await self.async_set_unique_id(udn)

        self.discovery_info.update({CONF_HOST: discovery_info[ATTR_SSDP_LOCATION]})

        return self.async_create_entry(
            title=discovery_info[ATTR_UPNP_FRIENDLY_NAME],
            data=self.discovery_info,
        )
