"""Support for FRITZ!Box devices."""

from __future__ import annotations

import datetime
import logging

from homeassistant.components.device_tracker import ScannerEntity, SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    AvmWrapper,
    FritzData,
    FritzDevice,
    FritzDeviceBase,
    device_filter_out_from_trackers,
)
from .const import DATA_FRITZ, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for FRITZ!Box component."""
    _LOGGER.debug("Starting FRITZ!Box device tracker")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]
    data_fritz: FritzData = hass.data[DATA_FRITZ]

    @callback
    def update_avm_device() -> None:
        """Update the values of AVM device."""
        _async_add_entities(avm_wrapper, async_add_entities, data_fritz)

    entry.async_on_unload(
        async_dispatcher_connect(hass, avm_wrapper.signal_device_new, update_avm_device)
    )

    update_avm_device()


@callback
def _async_add_entities(
    avm_wrapper: AvmWrapper,
    async_add_entities: AddEntitiesCallback,
    data_fritz: FritzData,
) -> None:
    """Add new tracker entities from the AVM device."""

    new_tracked = []
    if avm_wrapper.unique_id not in data_fritz.tracked:
        data_fritz.tracked[avm_wrapper.unique_id] = set()

    for mac, device in avm_wrapper.devices.items():
        if device_filter_out_from_trackers(mac, device, data_fritz.tracked.values()):
            continue

        new_tracked.append(FritzBoxTracker(avm_wrapper, device))
        data_fritz.tracked[avm_wrapper.unique_id].add(mac)

    async_add_entities(new_tracked)


class FritzBoxTracker(FritzDeviceBase, ScannerEntity):
    """Class which queries a FRITZ!Box device."""

    def __init__(self, avm_wrapper: AvmWrapper, device: FritzDevice) -> None:
        """Initialize a FRITZ!Box device."""
        super().__init__(avm_wrapper, device)
        self._last_activity: datetime.datetime | None = device.last_activity

    @property
    def is_connected(self) -> bool:
        """Return device status."""
        return self._avm_wrapper.devices[self._mac].is_connected

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return f"{self._mac}_tracker"

    @property
    def mac_address(self) -> str:
        """Return mac_address."""
        return self._mac

    @property
    def icon(self) -> str:
        """Return device icon."""
        if self.is_connected:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        device = self._avm_wrapper.devices[self._mac]
        self._last_activity = device.last_activity
        if self._last_activity is not None:
            attrs["last_time_reachable"] = self._last_activity.isoformat(
                timespec="seconds"
            )
        if device.connected_to:
            attrs["connected_to"] = device.connected_to
        if device.connection_type:
            attrs["connection_type"] = device.connection_type
        if device.ssid:
            attrs["ssid"] = device.ssid
        return attrs

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.ROUTER
