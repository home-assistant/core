"""Platform for device tracker integration."""
from __future__ import annotations

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import ConnectedStationInfo

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
    SourceType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNKNOWN, UnitOfFrequency
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import CONNECTED_WIFI_CLIENTS, DOMAIN, WIFI_APTYPE, WIFI_BANDS


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[
        str, DataUpdateCoordinator[list[ConnectedStationInfo]]
    ] = hass.data[DOMAIN][entry.entry_id]["coordinators"]
    registry = entity_registry.async_get(hass)
    tracked = set()

    @callback
    def new_device_callback() -> None:
        """Add new devices if needed."""
        new_entities = []
        for station in coordinators[CONNECTED_WIFI_CLIENTS].data:
            if station.mac_address in tracked:
                continue

            new_entities.append(
                DevoloScannerEntity(
                    coordinators[CONNECTED_WIFI_CLIENTS], device, station.mac_address
                )
            )
            tracked.add(station.mac_address)
            async_add_entities(new_entities)

    @callback
    def restore_entities() -> None:
        """Restore clients that are not a part of active clients list."""
        missing = []
        for entity in entity_registry.async_entries_for_config_entry(
            registry, entry.entry_id
        ):
            if (
                entity.platform == DOMAIN
                and entity.domain == DEVICE_TRACKER_DOMAIN
                and (
                    mac_address := entity.unique_id.replace(
                        f"{device.serial_number}_", ""
                    )
                )
                not in tracked
            ):
                missing.append(
                    DevoloScannerEntity(
                        coordinators[CONNECTED_WIFI_CLIENTS], device, mac_address
                    )
                )
                tracked.add(mac_address)

        async_add_entities(missing)

    if device.device and "wifi1" in device.device.features:
        restore_entities()
        entry.async_on_unload(
            coordinators[CONNECTED_WIFI_CLIENTS].async_add_listener(new_device_callback)
        )


class DevoloScannerEntity(
    CoordinatorEntity[DataUpdateCoordinator[list[ConnectedStationInfo]]], ScannerEntity
):
    """Representation of a devolo device tracker."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[list[ConnectedStationInfo]],
        device: Device,
        mac: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._device = device
        self._mac = mac

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        if not self.coordinator.data:
            return {}

        station = next(
            (
                station
                for station in self.coordinator.data
                if station.mac_address == self.mac_address
            ),
            None,
        )
        if station:
            attrs["wifi"] = WIFI_APTYPE.get(station.vap_type, STATE_UNKNOWN)
            attrs["band"] = (
                f"{WIFI_BANDS.get(station.band)} {UnitOfFrequency.GIGAHERTZ}"
                if WIFI_BANDS.get(station.band)
                else STATE_UNKNOWN
            )
        return attrs

    @property
    def icon(self) -> str:
        """Return device icon."""
        if self.is_connected:
            return "mdi:lan-connect"
        return "mdi:lan-disconnect"

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return any(
            station
            for station in self.coordinator.data
            if station.mac_address == self.mac_address
        )

    @property
    def mac_address(self) -> str:
        """Return mac_address."""
        return self._mac

    @property
    def source_type(self) -> SourceType:
        """Return tracker source type."""
        return SourceType.ROUTER

    @property
    def unique_id(self) -> str:
        """Return unique ID of the entity."""
        return f"{self._device.serial_number}_{self._mac}"
