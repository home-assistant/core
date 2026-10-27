"""Support for Keenetic routers as device tracker."""

import logging
from typing import Any, override

from ndms2_client import Device

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .router import KeeneticConfigEntry, KeeneticRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: KeeneticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Keenetic NDMS2 component."""
    router = config_entry.runtime_data

    tracked: set[str] = set()

    @callback
    def update_from_router():
        """Update the status of devices."""
        update_items(router, async_add_entities, tracked)

    update_from_router()

    registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    # Restore devices that are not a part of active clients list.
    restored = []
    for entity_entry in registry.entities.get_entries_for_config_entry_id(
        config_entry.entry_id
    ):
        if entity_entry.domain == DEVICE_TRACKER_DOMAIN:
            mac = entity_entry.unique_id.partition("_")[0]
            if mac not in tracked:
                tracked.add(mac)
                # Only set for trackers not added since their device carries the
                # client name, can be removed in HA Core 2027.5
                name = entity_entry.original_name
                if (
                    name is None
                    and entity_entry.device_id
                    and (device := device_registry.async_get(entity_entry.device_id))
                ):
                    name = device.name
                restored.append(
                    KeeneticTracker(
                        Device(
                            mac=mac,
                            name=name,
                            ip=None,
                            interface=None,
                        ),
                        router,
                    )
                )

    async_add_entities(restored)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, router.signal_update, update_from_router)
    )


@callback
def update_items(router: KeeneticRouter, async_add_entities, tracked: set[str]):
    """Update tracked device state from the hub."""
    new_tracked: list[KeeneticTracker] = []
    for mac, device in router.last_devices.items():
        if mac not in tracked:
            tracked.add(mac)
            new_tracked.append(KeeneticTracker(device, router))

    async_add_entities(new_tracked)


class KeeneticTracker(ScannerEntity):
    """Representation of network device."""

    _attr_should_poll = False

    def __init__(self, device: Device, router: KeeneticRouter) -> None:
        """Initialize the tracked device."""
        self._device = device
        self._router = router
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, device.mac)},
            name=device.name or device.mac,
        )
        self._last_seen = (
            dt_util.utcnow() if device.mac in router.last_devices else None
        )

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return (
            self._last_seen is not None
            and (dt_util.utcnow() - self._last_seen)
            < self._router.consider_home_interval
        )

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return f"{self._device.mac}_{self._router.config_entry.entry_id}"

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device.ip if self.is_connected else None

    @property
    @override
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac

    @property
    @override
    def available(self) -> bool:
        """Return if controller is available."""
        return self._router.available

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        if self.is_connected:
            return {
                "interface": self._device.interface,
            }
        return None

    @override
    async def async_added_to_hass(self) -> None:
        """Client entity created."""
        _LOGGER.debug(
            "New network device tracker %s (%s)", self.entity_id, self.unique_id
        )

        @callback
        def update_device() -> None:
            _LOGGER.debug(
                "Updating Keenetic tracked device %s (%s)",
                self.entity_id,
                self.unique_id,
            )
            new_device = self._router.last_devices.get(self._device.mac)
            if new_device:
                self._device = new_device
                self._last_seen = dt_util.utcnow()
                if (
                    new_device.name
                    and (device_entry := self.device_entry)
                    and device_entry.name != new_device.name
                ):
                    dr.async_get(self.hass).async_update_device(
                        device_entry.id, name=new_device.name
                    )

            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._router.signal_update, update_device
            )
        )
