"""Support for Zyxel routers."""
from __future__ import annotations

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import DATA_ZYXEL, DOMAIN
from .router import Zyxel_T50_Router, ZyxelDevice


async def async_setup_entry(
        hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up device tracker for Zyxel component."""
    router = hass.data[DOMAIN][entry.entry_id][DATA_ZYXEL]
    tracked = set()

    @callback
    def update_router():
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked)

    router.async_on_close(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


def add_entities(router, async_add_entities, tracked):
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(ZyxelTracker(router, device))
        tracked.add(mac)

    if new_tracked:
        async_add_entities(new_tracked)


class ZyxelTracker(ScannerEntity):
    """This class queries a Zyxel router."""

    def __init__(self, router: Zyxel_T50_Router, device: ZyxelDevice) -> None:
        """Initialize a Zyxel device."""
        self._router = router
        self._device = device

    @property
    def unique_id(self):
        """Return device unique id."""
        return self._device.mac

    @property
    def name(self):
        """Return device name."""
        return self._device.name

    @property
    def is_connected(self):
        """Return device status."""
        return self._device.is_connected

    @property
    def ip_address(self) -> str:
        """Return the primary ip address of the device."""
        return self._device.ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac

    @property
    def hostname(self) -> str:
        """Return hostname of the device."""
        return self._device.name

    @property
    def source_type(self) -> str:
        """Return tracker source type."""
        return SOURCE_TYPE_ROUTER

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information."""
        return {
            "connections": {(CONNECTION_NETWORK_MAC, self._device.mac)},
            "identifiers": {(DOMAIN, self.unique_id)},
            "default_name": self._device.name,
            "via_device": (
                DOMAIN,
                "Zyxel T-50",
            ),
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def icon(self):
        """Return device icon."""
        if self.is_connected:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        if self._device.last_activity is not None:
            attrs["last_time_reachable"] = self._device.last_activity.isoformat(
                timespec="seconds"
            )
        return attrs

    @callback
    def async_on_demand_update(self):
        """Update state."""
        self._device = self._router.devices[self._device.mac]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )
