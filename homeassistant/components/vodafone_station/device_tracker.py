"""Support for Vodafone Station routers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _LOGGER, DEFAULT_DEVICE_NAME, DOMAIN
from .coordinator import VodafoneStationDeviceInfo, VodafoneStationRouter


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Vodafone Station component."""

    _LOGGER.debug("Start device trackers setup")
    coordinator: VodafoneStationRouter = hass.data[DOMAIN][entry.entry_id]

    tracked: set = set()

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        add_entities(coordinator, async_add_entities, tracked)

    entry.async_on_unload(
        async_dispatcher_connect(hass, coordinator.signal_device_new, update_router)
    )

    update_router()


@callback
def add_entities(
    coordinator: VodafoneStationRouter,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    _LOGGER.debug("Adding device trackers entities")
    for mac, device in coordinator.data["devices"].items():
        if mac in tracked:
            continue
        _LOGGER.debug("New device tracker: %s", device.hostname)
        new_tracked.append(VodafoneStationTracker(coordinator, device))
        tracked.add(mac)

    async_add_entities(new_tracked)


class VodafoneStationTracker(CoordinatorEntity[VodafoneStationRouter], ScannerEntity):
    """Representation of a Vodafone Station device."""

    def __init__(
        self, coordinator: VodafoneStationRouter, device: VodafoneStationDeviceInfo
    ) -> None:
        """Initialize a Vodafone Station device."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._device_mac = device._mac
        self._attr_unique_id = device._mac
        self._attr_name = device._name or DEFAULT_DEVICE_NAME

    @property
    def _device_info(self) -> VodafoneStationDeviceInfo:
        """Return fresh data for the device."""
        return self.coordinator.data["devices"][self._device_mac]

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device_info.is_connected

    @property
    def source_type(self) -> SourceType:
        """Return the source type."""
        return SourceType.ROUTER

    @property
    def hostname(self) -> str | None:
        """Return the hostname of device."""
        return self._attr_name

    @property
    def icon(self) -> str:
        """Return device icon."""
        return (
            "mdi:lan-connect"
            if self._device_info.is_connected
            else "mdi:lan-disconnect"
        )

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device_info.ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device_info.mac_address

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes of the device."""
        self._attr_extra_state_attributes = {}
        self._attr_extra_state_attributes[
            "connection_type"
        ] = self._device_info.connection_type
        if "Wifi" in self._device_info.connection_type:
            self._attr_extra_state_attributes["wifi_band"] = self._device_info.wifi
        self._attr_extra_state_attributes[
            "last_time_reachable"
        ] = self._device_info.last_activity
        return super().extra_state_attributes

    async def async_process_update(self) -> None:
        """Update device."""
        raise NotImplementedError()

    async def async_on_demand_update(self) -> None:
        """Update state."""
        await self.async_process_update()
        self.async_write_ha_state()
