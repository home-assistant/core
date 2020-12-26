"""Constants for the Terncy integration."""

import ipaddress
import logging

from zeroconf import ServiceBrowser

from homeassistant.components import zeroconf as hasszeroconf

from .const import (
    TERNCY_EVENT_SVC_ADD,
    TERNCY_EVENT_SVC_REMOVE,
    TERNCY_EVENT_SVC_UPDATE,
    TERNCY_HUB_SVC_NAME,
)

_LOGGER = logging.getLogger(__name__)


class TerncyZCListener:
    """Terncy zeroconf discovery listener."""

    def __init__(self, manager):
        """Create terncy discovery listener."""
        self.manager = manager

    def _parse_svc(self, dev_id, info):
        txt_records = {"dev_id": dev_id}
        ip = ""
        if len(info.addresses) > 0:
            if len(info.addresses[0]) == 4:
                ip = str(ipaddress.IPv4Address(info.addresses[0]))
            if len(info.addresses[0]) == 16:
                ip = str(ipaddress.IPv6Address(info.addresses[0]))
        txt_records["ip"] = ip
        txt_records["port"] = info.port
        for k in info.properties:
            txt_records[k.decode("utf-8")] = info.properties[k].decode("utf-8")
        return txt_records

    def remove_service(self, zc, svc_type, name):
        """Get a terncy service removed event."""
        dev_id = name.replace("." + svc_type, "")
        if dev_id in self.manager.hubs:
            del self.manager.hubs[dev_id]
        txt_records = {"dev_id": dev_id}
        self.manager.hass.bus.async_fire(TERNCY_EVENT_SVC_REMOVE, txt_records)

    def update_service(self, zc, svc_type, name):
        """Get a terncy service updated event."""
        info = zc.get_service_info(svc_type, name)
        dev_id = name.replace("." + svc_type, "")
        txt_records = self._parse_svc(dev_id, info)

        self.manager.hubs[dev_id] = txt_records
        self.manager.hass.bus.async_fire(TERNCY_EVENT_SVC_UPDATE, txt_records)

    def add_service(self, zc, svc_type, name):
        """Get a new terncy service discovered event."""
        info = zc.get_service_info(svc_type, name)
        dev_id = name.replace("." + svc_type, "")
        txt_records = self._parse_svc(dev_id, info)

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
            zc = await hasszeroconf.async_get_instance(self.hass)
            self._discovery_engine = zc
            listener = TerncyZCListener(self)
            self._browser = ServiceBrowser(zc, TERNCY_HUB_SVC_NAME, listener)

    async def stop_discovery(self):
        """Stop terncy discovery engine."""
        if self._discovery_engine:
            self._browser.cancel()
            self._discovery_engine.close()
            self._browser = None
            self._discovery_engine = None
