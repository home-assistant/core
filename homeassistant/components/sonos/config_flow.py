"""Config flow for SONOS."""

from collections.abc import Awaitable

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DATA_SONOS_DISCOVERY_MANAGER, DOMAIN, UPNP_ST
from .helpers import hostname_to_uid


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if Sonos devices have been seen recently with SSDP."""
    return bool(await ssdp.async_get_discovery_info_by_st(hass, UPNP_ST))


class SonosDiscoveryFlowHandler(DiscoveryFlowHandler[Awaitable[bool]], domain=DOMAIN):
    """Sonos discovery flow that callsback zeroconf updates."""

    def __init__(self) -> None:
        """Init discovery flow."""
        super().__init__(DOMAIN, "Sonos", _async_has_devices)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a flow initialized by zeroconf."""
        hostname = discovery_info.hostname
        if hostname is None or not hostname.lower().startswith("sonos"):
            return self.async_abort(reason="not_sonos_device")
        if discovery_info.ip_address.version != 4:
            return self.async_abort(reason="not_ipv4_address")
        if discovery_manager := self.hass.data.get(DATA_SONOS_DISCOVERY_MANAGER):
            host = discovery_info.host
            mdns_name = discovery_info.name
            properties = discovery_info.properties
            boot_seqnum = properties.get("bootseq")
            model = properties.get("model")
            uid = hostname_to_uid(hostname)
            discovery_manager.async_discovered_player(
                "Zeroconf", properties, host, uid, boot_seqnum, model, mdns_name
            )
        await self.async_set_unique_id(self._domain, raise_on_progress=False)
        return await self.async_step_discovery({})
