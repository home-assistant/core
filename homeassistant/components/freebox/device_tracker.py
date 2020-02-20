"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from datetime import datetime
import logging
from typing import Dict

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .const import DEFAULT_DEVICE_NAME, DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_get_scanner(hass, config):
    """Old way of setting up the platform."""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the device_tracker."""
    fbx = hass.data[DOMAIN]

    entities = []

    for device in fbx.devices.values():
        entities.append(device)

    async_add_entities(entities)


class FreeboxDevice(TrackerEntity):
    """Representation of a Freebox device."""

    def __init__(self, device: Dict[str, any]):
        """Initialize a Freebox device."""
        self._name = device["primary_name"].strip() or DEFAULT_DEVICE_NAME
        self._mac = device["l2ident"]["id"]
        self._manufacturer = device["vendor_name"]
        self._icon = icon_for_freebox_device(device)
        self._unsub_dispatcher = None

        self.update_state(device)

    def update_state(self, device: Dict[str, any]) -> None:
        """Update the Freebox device."""
        self._active = device["active"]
        if device.get("attrs") is None:
            # device
            self._reachable = device["reachable"]
            self._attrs = {
                "reachable": self._reachable,
                "last_time_reachable": datetime.fromtimestamp(
                    device["last_time_reachable"]
                ),
                "last_time_activity": datetime.fromtimestamp(device["last_activity"]),
            }
        else:
            # router
            self._attrs = device["attrs"]

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self.mac

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def latitude(self):
        """Return the latitude."""
        if self.active:
            return self.hass.config.latitude
        return None

    @property
    def longitude(self):
        """Return the longitude."""
        if self.active:
            return self.hass.config.longitude
        return None

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def mac(self) -> str:
        """Return the MAC address."""
        return self._mac

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer."""
        return self._manufacturer

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def active(self) -> bool:
        """Return true if the host sends traffic to the Freebox."""
        return self._active

    @property
    def reachable(self) -> bool:
        """Return true if the host can receive traffic from the Freebox."""
        return self._reachable

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return the attributes."""
        return self._attrs

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self.mac)},
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": self.manufacturer,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, TRACKER_UPDATE, self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()


def icon_for_freebox_device(device) -> str:
    """Return a host icon from his type."""
    switcher = {
        "freebox_delta": "mdi:television-guide",
        "freebox_hd": "mdi:television-guide",
        "freebox_mini": "mdi:television-guide",
        "freebox_player": "mdi:television-guide",
        "ip_camera": "mdi:cctv",
        "ip_phone": "mdi:phone-voip",
        "laptop": "mdi:laptop",
        "multimedia_device": "mdi:play-network",
        "nas": "mdi:nas",
        "networking_device": "mdi:network",
        "printer": "mdi:printer",
        "router": "mdi:router-wireless",
        "smartphone": "mdi:cellphone",
        "tablet": "mdi:tablet",
        "television": "mdi:television",
        "vg_console": "mdi:gamepad-variant",
        "workstation": "mdi:desktop-tower-monitor",
    }

    return switcher.get(device["host_type"], "mdi:help-network")
