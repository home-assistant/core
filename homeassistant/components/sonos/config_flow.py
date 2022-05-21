"""Config flow for SONOS."""
from collections.abc import Awaitable
import dataclasses

from homeassistant.components import ssdp, zeroconf
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.config_entry_flow import DiscoveryFlowHandler

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
        self, discovery_info: zeroconf.ZeroconfServiceInfo
    ) -> FlowResult:
        """Handle a flow initialized by zeroconf."""
        hostname = discovery_info.hostname
        if hostname is None or not hostname.lower().startswith("sonos"):
            return self.async_abort(reason="not_sonos_device")
        await self.async_set_unique_id(self._domain, raise_on_progress=False)
        host = discovery_info.host
        mdns_name = discovery_info.name
        properties = discovery_info.properties
        boot_seqnum = properties.get("bootseq")
        model = properties.get("model")
        uid = hostname_to_uid(hostname)
        if discovery_manager := self.hass.data.get(DATA_SONOS_DISCOVERY_MANAGER):
            discovery_manager.async_discovered_player(
                "Zeroconf", properties, host, uid, boot_seqnum, model, mdns_name
            )
        return await self.async_step_discovery(dataclasses.asdict(discovery_info))
