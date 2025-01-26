"""Support for Vodafone Station routers."""

from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _LOGGER, DOMAIN
from .coordinator import VodafoneStationDeviceInfo, VodafoneStationRouter


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up device tracker for Vodafone Station component."""

    _LOGGER.debug("Start device trackers setup")
    coordinator: VodafoneStationRouter = hass.data[DOMAIN][entry.entry_id]

    tracked: set = set()

    @callback
    def async_update_router() -> None:
        """Update the values of the router."""
        async_add_new_tracked_entities(coordinator, async_add_entities, tracked)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, coordinator.signal_device_new, async_update_router
        )
    )

    async_update_router()


@callback
def async_add_new_tracked_entities(
    coordinator: VodafoneStationRouter,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new tracker entities from the router."""
    new_tracked = []

    _LOGGER.debug("Adding device trackers entities")
    for mac, device_info in coordinator.data.devices.items():
        if mac in tracked:
            continue
        _LOGGER.debug("New device tracker: %s", device_info.device.name)
        new_tracked.append(VodafoneStationTracker(coordinator, device_info))
        tracked.add(mac)

    async_add_entities(new_tracked)


class VodafoneStationTracker(CoordinatorEntity[VodafoneStationRouter], ScannerEntity):
    """Representation of a Vodafone Station device."""

    _attr_translation_key = "device_tracker"
    mac_address: str

    def __init__(
        self, coordinator: VodafoneStationRouter, device_info: VodafoneStationDeviceInfo
    ) -> None:
        """Initialize a Vodafone Station device."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        mac = device_info.device.mac
        self._attr_mac_address = mac
        self._attr_unique_id = mac
        self._attr_hostname = device_info.device.name or mac.replace(":", "_")

    @property
    def _device_info(self) -> VodafoneStationDeviceInfo:
        """Return fresh data for the device."""
        return self.coordinator.data.devices[self.mac_address]

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self._device_info.home

    @property
    def ip_address(self) -> str | None:
        """Return the primary ip address of the device."""
        return self._device_info.device.ip_address
