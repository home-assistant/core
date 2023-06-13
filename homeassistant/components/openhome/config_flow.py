"""Config flow for Linn / OpenHome."""

import logging

from homeassistant.components.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _is_complete_discovery(discovery_info: SsdpServiceInfo) -> bool:
    """Test if discovery is complete and usable."""
    return bool(ATTR_UPNP_UDN in discovery_info.upnp and discovery_info.ssdp_location)


class OpenhomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle an Openhome config flow."""

    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Handle a flow initialized by discovery."""
        _LOGGER.debug("async_step_ssdp: started")

        if not _is_complete_discovery(discovery_info):
            _LOGGER.debug("async_step_ssdp: Incomplete discovery, ignoring")
            return self.async_abort(reason="incomplete_discovery")

        _LOGGER.debug(
            "async_step_ssdp: setting unique id %s", discovery_info.upnp[ATTR_UPNP_UDN]
        )

        await self.async_set_unique_id(discovery_info.upnp[ATTR_UPNP_UDN])
        self._abort_if_unique_id_configured({CONF_HOST: discovery_info.ssdp_location})

        _LOGGER.debug(
            "async_step_ssdp: create entry %s", discovery_info.upnp[ATTR_UPNP_UDN]
        )

        return self.async_create_entry(
            title=discovery_info.upnp[ATTR_UPNP_FRIENDLY_NAME],
            data={CONF_HOST: discovery_info.ssdp_location},
        )
