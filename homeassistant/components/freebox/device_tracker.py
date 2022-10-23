"""Support for Freebox devices (Freebox v6 and Freebox mini 4K)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_DEVICE_NAME, DEVICE_ICONS, DOMAIN
from .router import FreeboxRouter


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Freebox component."""
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]
    tracked: set[str] = set()

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked)

    entry.async_on_unload(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


@callback
def add_entities(
    router: FreeboxRouter, async_add_entities: AddEntitiesCallback, tracked: set[str]
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(FreeboxDevice(router, device))
        tracked.add(mac)

    async_add_entities(new_tracked, True)


class FreeboxDevice(ScannerEntity):
    """Representation of a Freebox device."""

    _attr_should_poll = False

    def __init__(self, router: FreeboxRouter, device: dict[str, Any]) -> None:
        """Initialize a Freebox device."""
        self._router = router
        self._name = device["primary_name"].strip() or DEFAULT_DEVICE_NAME
        self._mac = device["l2ident"]["id"]
        self._manufacturer = device["vendor_name"]
        self._icon = icon_for_freebox_device(device)
        self._active = False
        self._attrs: dict[str, Any] = {}

    @callback
    def async_update_state(self) -> None:
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
    def mac_address(self) -> str:
        """Return a unique ID."""
        return self._mac

    @property
    def name(self) -> str:
        """Return the name."""
        return self._name

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._active

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.ROUTER

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the attributes."""
        return self._attrs

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self.async_update_state()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_update_state()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )


def icon_for_freebox_device(device) -> str:
    """Return a device icon from its type."""
    return DEVICE_ICONS.get(device["host_type"], "mdi:help-network")
