"""Constants for the Terncy integration."""

import ipaddress
import logging

from zeroconf import ServiceBrowser

from homeassistant.components import zeroconf as hasszeroconf

from .const import (
    CONF_DEVID,
    CONF_IP,
    CONF_PORT,
    TERNCY_EVENT_SVC_ADD,
    TERNCY_EVENT_SVC_REMOVE,
    TERNCY_EVENT_SVC_UPDATE,
    TERNCY_HUB_SVC_NAME,
)

_LOGGER = logging.getLogger(__name__)


def _parse_svc(dev_id, info):
    txt_records = {CONF_DEVID: dev_id}
    ip_addr = ""
    if len(info.addresses) > 0:
        if len(info.addresses[0]) == 4:
            ip_addr = str(ipaddress.IPv4Address(info.addresses[0]))
        if len(info.addresses[0]) == 16:
            ip_addr = str(ipaddress.IPv6Address(info.addresses[0]))
    txt_records[CONF_IP] = ip_addr
    txt_records[CONF_PORT] = info.port
    for k in info.properties:
        txt_records[k.decode("utf-8")] = info.properties[k].decode("utf-8")
    return txt_records


class TerncyZCListener:
    """Terncy zeroconf discovery listener."""

    def __init__(self, manager):
        """Create Terncy discovery listener."""
        self.manager = manager

    def remove_service(self, zconf, svc_type, name):
        """Get a terncy service removed event."""
        dev_id = name.replace("." + svc_type, "")
        if dev_id in self.manager.hubs:
            del self.manager.hubs[dev_id]
        txt_records = {CONF_DEVID: dev_id}
        self.manager.hass.bus.async_fire(TERNCY_EVENT_SVC_REMOVE, txt_records)

    def update_service(self, zconf, svc_type, name):
        """Get a terncy service updated event."""
        info = zconf.get_service_info(svc_type, name)
        if info is None:
            return
        dev_id = name.replace("." + svc_type, "")
        txt_records = _parse_svc(dev_id, info)

        self.manager.hubs[dev_id] = txt_records
        self.manager.hass.bus.async_fire(TERNCY_EVENT_SVC_UPDATE, txt_records)

    def add_service(self, zconf, svc_type, name):
        """Get a new terncy service discovered event."""
        info = zconf.get_service_info(svc_type, name)
        if info is None:
            return
        dev_id = name.replace("." + svc_type, "")
        txt_records = _parse_svc(dev_id, info)

        self.manager.hubs[dev_id] = txt_records
        self.manager.hass.bus.async_fire(TERNCY_EVENT_SVC_ADD, txt_records)


class TerncyHubManager:
    """Manager of terncy hubs."""

    __instance = None

    def __init__(self, hass):
        """Create instance of terncy manager, use instance instead."""
        self.hass = hass
        self._browser = None
        self._discovery_engine = None
        self.hubs = {}
        TerncyHubManager.__instance = self

    @staticmethod
    def instance(hass):
        """Get singleton instance of terncy manager."""
        if TerncyHubManager.__instance is None:
            TerncyHubManager(hass)
        return TerncyHubManager.__instance

    async def start_discovery(self):
        """Start terncy discovery engine."""
        if not self._discovery_engine:
            zconf = await hasszeroconf.async_get_instance(self.hass)
            self._discovery_engine = zconf
            listener = TerncyZCListener(self)
            self._browser = ServiceBrowser(zconf, TERNCY_HUB_SVC_NAME, listener)

    async def stop_discovery(self):
        """Stop terncy discovery engine."""
        if self._discovery_engine:
            self._browser.cancel()
            self._discovery_engine.close()
            self._browser = None
            self._discovery_engine = None
