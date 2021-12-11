"""Support for FRITZ!Box routers."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.device_tracker import SOURCE_TYPE_ROUTER
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import (
    FritzBoxTools,
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
    router: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]
    data_fritz: FritzData = hass.data[DATA_FRITZ]

    @callback
    def update_router() -> None:
        """Update the values of the router."""
        _async_add_entities(router, async_add_entities, data_fritz)

    entry.async_on_unload(
        async_dispatcher_connect(hass, router.signal_device_new, update_router)
    )

    update_router()


@callback
def _async_add_entities(
    router: FritzBoxTools,
    async_add_entities: AddEntitiesCallback,
    data_fritz: FritzData,
) -> None:
    """Add new tracker entities from the router."""

    new_tracked = []
    if router.unique_id not in data_fritz.tracked:
        data_fritz.tracked[router.unique_id] = set()

    for mac, device in router.devices.items():
        if device_filter_out_from_trackers(mac, device, data_fritz.tracked.values()):
            continue

        new_tracked.append(FritzBoxTracker(router, device))
        data_fritz.tracked[router.unique_id].add(mac)

    if new_tracked:
        async_add_entities(new_tracked)


class FritzBoxTracker(FritzDeviceBase, ScannerEntity):
    """This class queries a FRITZ!Box router."""

    def __init__(self, router: FritzBoxTools, device: FritzDevice) -> None:
        """Initialize a FRITZ!Box device."""
        super().__init__(router, device)
        self._last_activity: datetime.datetime | None = device.last_activity
        self._active = False

    @property
    def is_connected(self) -> bool:
        """Return device status."""
        return self._active

    @property
    def unique_id(self) -> str:
        """Return device unique id."""
        return f"{self._mac}_tracker"

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
        if self._last_activity is not None:
            attrs["last_time_reachable"] = self._last_activity.isoformat(
                timespec="seconds"
            )
        return attrs

    @property
    def source_type(self) -> str:
        """Return tracker source type."""
        return SOURCE_TYPE_ROUTER

    async def async_process_update(self) -> None:
        """Update device."""
        if not self._mac:
            return

        device = self._router.devices[self._mac]
        self._active = device.is_connected
        self._last_activity = device.last_activity
