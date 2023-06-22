"""Support for Vodafone Station routers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import VodafoneStationApi, VodafoneStationDeviceInfo
from .const import _LOGGER, DEFAULT_DEVICE_NAME, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Vodafone Station component."""

    _LOGGER.debug("Start device trackers setup")
    api: VodafoneStationApi = hass.data[DOMAIN][entry.entry_id]

    tracked: set = set()

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        add_entities(api, async_add_entities, tracked)

    entry.async_on_unload(
        async_dispatcher_connect(hass, api.signal_device_new, update_router)
    )

    update_router()


@callback
def add_entities(
    api: VodafoneStationApi, async_add_entities: AddEntitiesCallback, tracked: set[str]
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    _LOGGER.debug("Adding device trackers entities")
    for mac, device in api.devices.items():
        if mac in tracked:
            continue
        _LOGGER.debug("New device tracker: %s", device.hostname)
        new_tracked.append(VodafoneStationTracker(api, device))
        tracked.add(mac)

    async_add_entities(new_tracked)


class VodafoneStationTracker(ScannerEntity):
    """Representation of a Vodafone Station device."""

    _attr_should_poll = True

    def __init__(
        self, api: VodafoneStationApi, device: VodafoneStationDeviceInfo
    ) -> None:
        """Initialize a Vodafone Station device."""
        self._api = api
        self._device: VodafoneStationDeviceInfo = device
        self._attr_unique_id = device._mac
        self._attr_name = device._name or DEFAULT_DEVICE_NAME

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device.is_connected

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
        return "mdi:lan-connect" if self._device.is_connected else "mdi:lan-disconnect"

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device.ip_address

    @property
    def mac_address(self) -> str:
        """Return the mac address of the device."""
        return self._device.mac_address

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional attributes of the device."""
        dev = self._api.devices[self.mac_address]
        self._attr_extra_state_attributes = {}
        self._attr_extra_state_attributes["connection_type"] = dev.connection_type
        if "Wifi" in dev.connection_type:
            self._attr_extra_state_attributes["wifi_band"] = dev.wifi
        self._attr_extra_state_attributes["last_time_reachable"] = dev.last_activity
        return super().extra_state_attributes

    @callback
    def async_on_demand_update(self) -> None:
        """Update state."""
        self._device = self._api.devices[self._device.mac_address]
        self._attr_extra_state_attributes = {}
        if self._device.last_activity:
            self._attr_extra_state_attributes[
                "last_time_reachable"
            ] = self._device.last_activity.isoformat(timespec="seconds")
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._api.signal_device_update,
                self.async_on_demand_update,
            )
        )
