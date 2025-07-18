"""Platform for device tracker integration."""

from __future__ import annotations

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import ConnectedStationInfo

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.const import STATE_UNKNOWN, UnitOfFrequency
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONNECTED_WIFI_CLIENTS, DOMAIN, WIFI_APTYPE, WIFI_BANDS
from .coordinator import DevoloDataUpdateCoordinator, DevoloHomeNetworkConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeNetworkConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device = entry.runtime_data.device
    coordinators: dict[
        str, DevoloDataUpdateCoordinator[dict[str, ConnectedStationInfo]]
    ] = entry.runtime_data.coordinators
    registry = er.async_get(hass)
    tracked = set()

    @callback
    def new_device_callback() -> None:
        """Add new devices if needed."""
        new_entities = []
        for mac_address in coordinators[CONNECTED_WIFI_CLIENTS].data:
            if mac_address in tracked:
                continue

            new_entities.append(
                DevoloScannerEntity(
                    coordinators[CONNECTED_WIFI_CLIENTS], device, mac_address
                )
            )
            tracked.add(mac_address)
        async_add_entities(new_entities)

    @callback
    def restore_entities() -> None:
        """Restore clients that are not a part of active clients list."""
        missing = []
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
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

    restore_entities()
    entry.async_on_unload(
        coordinators[CONNECTED_WIFI_CLIENTS].async_add_listener(new_device_callback)
    )


# The pylint disable is needed because of https://github.com/pylint-dev/pylint/issues/9138
class DevoloScannerEntity(  # pylint: disable=hass-enforce-class-module
    CoordinatorEntity[DevoloDataUpdateCoordinator[dict[str, ConnectedStationInfo]]],
    ScannerEntity,
):
    """Representation of a devolo device tracker."""

    _attr_has_entity_name = True
    _attr_translation_key = "device_tracker"

    def __init__(
        self,
        coordinator: DevoloDataUpdateCoordinator[dict[str, ConnectedStationInfo]],
        device: Device,
        mac: str,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_mac_address = mac
        self._attr_name = mac

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the attributes."""
        attrs: dict[str, str] = {}
        if not self.coordinator.data:
            return {}

        assert self.mac_address
        station = self.coordinator.data.get(self.mac_address)
        if station:
            attrs["wifi"] = WIFI_APTYPE.get(station.vap_type, STATE_UNKNOWN)
            attrs["band"] = (
                f"{WIFI_BANDS.get(station.band)} {UnitOfFrequency.GIGAHERTZ}"
                if WIFI_BANDS.get(station.band)
                else STATE_UNKNOWN
            )
        return attrs

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        assert self.mac_address
        return self.coordinator.data.get(self.mac_address) is not None

    @property
    def unique_id(self) -> str:
        """Return unique ID of the entity."""
        return f"{self._device.serial_number}_{self.mac_address}"
