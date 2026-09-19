"""Support for Xiaomi Mi WiFi Repeater 2."""

import logging
from typing import override

from miio.wifirepeater import WifiRepeaterStatus

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .typing import XiaomiMiioConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiMiioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device tracker platform for a Xiaomi Mi WiFi Repeater 2."""
    coordinator = entry.runtime_data.device_coordinator
    tracked: dict[str, XiaomiMiioRepeaterDevice] = {}

    # Restore entities for devices that were previously seen but are not
    # currently connected, so they keep reporting not_home instead of vanishing.
    entity_registry = er.async_get(hass)
    # unique_id is f"{entry_id}_{mac}". format_mac passes unknown formats
    # through unchanged, so the prefix is matched explicitly.
    prefix = f"{entry.entry_id}_"
    restore_entities: list[XiaomiMiioRepeaterDevice] = []
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.domain != "device_tracker" or not entity_entry.unique_id:
            continue
        if not entity_entry.unique_id.startswith(prefix):
            continue
        mac = format_mac(entity_entry.unique_id.removeprefix(prefix))
        if mac not in tracked:
            tracked[mac] = entity = XiaomiMiioRepeaterDevice(coordinator, mac)
            restore_entities.append(entity)
    if restore_entities:
        async_add_entities(restore_entities)

    @callback
    def add_tracked_entities() -> None:
        """Add entities for stations that are connected but not yet tracked."""
        add_entities(coordinator, coordinator.data, async_add_entities, tracked)

    entry.async_on_unload(coordinator.async_add_listener(add_tracked_entities))
    add_tracked_entities()


@callback
def add_entities(
    coordinator: DataUpdateCoordinator[WifiRepeaterStatus],
    station_info: WifiRepeaterStatus | None,
    async_add_entities: AddConfigEntryEntitiesCallback,
    tracked: dict[str, XiaomiMiioRepeaterDevice],
) -> None:
    """Add new tracker entities for devices connected to the repeater."""
    if station_info is None:
        return

    new_tracked: list[XiaomiMiioRepeaterDevice] = []
    for station in station_info.associated_stations:
        if not isinstance(station, dict):
            continue
        try:
            mac = format_mac(station["mac"])
        except KeyError, TypeError, ValueError:
            _LOGGER.debug("Skipping station with invalid MAC address: %s", station)
            continue
        if mac in tracked:
            continue
        tracked[mac] = entity = XiaomiMiioRepeaterDevice(coordinator, mac)
        new_tracked.append(entity)

    if new_tracked:
        async_add_entities(new_tracked)


class XiaomiMiioRepeaterDevice(ScannerEntity):
    """Representation of a device connected to a Xiaomi Mi WiFi Repeater 2."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[WifiRepeaterStatus],
        mac: str,
    ) -> None:
        """Initialize the entity.

        The repeater does not expose the name of the associated device,
        so the MAC address is used as the entity name.
        """
        self._coordinator = coordinator
        self._mac = mac
        # Scoped to the config entry: the same client can be connected to
        # multiple configured repeaters.
        assert coordinator.config_entry is not None
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{mac}"
        self._attr_name = mac
        self._attr_mac_address = mac
        self._attr_ip_address: str | None = None
        self._connected = False
        # add_to_platform_start runs before async_added_to_hass and reads
        # is_connected/ip_address for connected-device discovery.
        self.async_update_state()

    @property
    @override
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._attr_unique_id

    @callback
    def async_update_state(self) -> None:
        """Update the state from the latest station list."""
        self._connected = False
        self._attr_ip_address = None
        data = self._coordinator.data
        if data is None:
            return
        for station in data.associated_stations:
            if not isinstance(station, dict):
                continue
            try:
                station_mac = format_mac(station["mac"])
            except KeyError, TypeError, ValueError:
                continue
            if station_mac == self._mac:
                self._connected = True
                self._attr_ip_address = station.get("ip")
                break

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the repeater."""
        return self._connected

    @callback
    def async_on_demand_update(self) -> None:
        """Update state from the latest station list."""
        self.async_update_state()
        self.async_write_ha_state()

    @override
    async def async_added_to_hass(self) -> None:
        """Register state update callback."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_on_demand_update)
        )
