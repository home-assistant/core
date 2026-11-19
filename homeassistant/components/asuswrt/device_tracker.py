"""Support for ASUSWRT routers."""

from typing import TYPE_CHECKING, override

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AsusWrtConfigEntry
from .router import AsusWrtDevInfo, AsusWrtRouter, unnamed_client_name


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AsusWrtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for AsusWrt component."""
    router = entry.runtime_data
    tracked: set = set()

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        add_entities(router, async_add_entities, tracked)

    @callback
    def forget_device(mac: str) -> None:
        """Let a removed client get a new tracker when it connects again."""
        tracked.discard(mac)

    router.async_on_close(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )
    router.async_on_close(
        async_dispatcher_connect(hass, router.signal_device_removed, forget_device)
    )

    update_router()


@callback
def add_entities(
    router: AsusWrtRouter,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    for mac, device in router.devices.items():
        if mac in tracked:
            continue

        new_tracked.append(AsusWrtDevice(router, device))
        tracked.add(mac)

    async_add_entities(new_tracked)


class AsusWrtDevice(ScannerEntity):
    """Representation of a AsusWrt device."""

    _attr_should_poll = False

    def __init__(self, router: AsusWrtRouter, device: AsusWrtDevInfo) -> None:
        """Initialize a AsusWrt device."""
        self._router = router
        self._device = device
        self._attr_name = device.name or unnamed_client_name(device.mac)

    @override
    async def async_prepare_to_add_to_hass(self) -> None:
        """Describe the device before it is created or updated."""
        if TYPE_CHECKING:
            assert self.platform.config_entry is not None
        connection = (dr.CONNECTION_NETWORK_MAC, self._device.mac)
        # The MAC address only names a new device, an existing one keeps its name
        if not (name := self._device.name) and not dr.async_get(
            self.hass
        ).async_get_device_by_connection(
            connection, self.platform.config_entry.entry_id
        ):
            name = self._device.mac
        self._attr_device_info = dr.DeviceInfo(connections={connection})
        if name:
            self._attr_device_info.name = name
        await super().async_prepare_to_add_to_hass()

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device.is_connected

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of device."""
        return self._device.name

    @property
    @override
    def icon(self) -> str:
        """Return device icon."""
        return "mdi:lan-connect" if self._device.is_connected else "mdi:lan-disconnect"

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device.ip_address

    @property
    @override
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac

    @callback
    def async_on_demand_update(self) -> None:
        """Update state."""
        self._device = self._router.devices[self._device.mac]
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._router.signal_device_update,
                self.async_on_demand_update,
            )
        )
