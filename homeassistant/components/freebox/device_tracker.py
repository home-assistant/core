"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from datetime import datetime
import logging
from typing import Dict

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .const import DEFAULT_DEVICE_NAME, DEVICE_ICONS, DOMAIN
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for Freebox component."""
    router = hass.data[DOMAIN][entry.unique_id]
    tracked = set()

    @callback
    def update_router():
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


@callback
def add_entities(router, async_add_entities, tracked):
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(FreeboxDevice(router, device))
        tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked, True)


class FreeboxDevice(ScannerEntity):
    """Representation of a Freebox device."""

    def __init__(self, router: FreeboxRouter, device: Dict[str, any]) -> None:
        """Initialize a Freebox device."""
        self._router = router
        self._name = device["primary_name"].strip() or DEFAULT_DEVICE_NAME
        self._mac = device["l2ident"]["id"]
        self._manufacturer = device["vendor_name"]
        self._icon = icon_for_freebox_device(device)
        self._active = False
        self._attrs = {}

        self._unsub_dispatcher = None

    def update(self) -> None:
        """Update the Freebox device."""
        device = self._router.devices[self._mac]
        self._active = device["active"]
        if device.get("attrs") is None:
            # device
            self._attrs = {
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
        return self._mac

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def is_connected(self):
        """Return true if the device is connected to the network."""
        return self._active

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def device_state_attributes(self) -> Dict[str, any]:
        """Return the attributes."""
        return self._attrs

    @property
    def device_info(self) -> Dict[str, any]:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._mac)},
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": self._manufacturer,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_on_demand_update(self):
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register state update callback."""
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self._router.signal_device_update, self.async_on_demand_update
        )

    async def async_will_remove_from_hass(self):
        """Clean up after entity before removal."""
        self._unsub_dispatcher()


def icon_for_freebox_device(device) -> str:
    """Return a host icon from his type."""
    return DEVICE_ICONS.get(device["host_type"], "mdi:help-network")
