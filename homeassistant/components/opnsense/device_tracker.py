"""Device tracker support for OPNsense routers."""

from __future__ import annotations

import logging
from typing import Any, NewType

from pyopnsense import diagnostics

from homeassistant.components.device_tracker import DeviceScanner, ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    CONF_TRACKER_MAC_ADDRESSES,
    DOMAIN,
    OPNSENSE_DATA,
)
from .coordinator import OPNsenseDataUpdateCoordinator

DeviceDetails = NewType("DeviceDetails", dict[str, Any])
DeviceDetailsByMAC = NewType("DeviceDetailsByMAC", dict[str, DeviceDetails])


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> DeviceScanner | None:
    """Configure the OPNsense device_tracker (legacy YAML)."""
    if OPNSENSE_DATA not in hass.data:
        return None
    return OPNsenseDeviceScanner(
        hass.data[OPNSENSE_DATA][CONF_INTERFACE_CLIENT],
        hass.data[OPNSENSE_DATA][CONF_TRACKER_INTERFACES],
        hass.data[OPNSENSE_DATA].get(CONF_TRACKER_MAC_ADDRESSES, []),
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker for OPNsense component."""
    data = hass.data[OPNSENSE_DATA][entry.entry_id]
    coordinator: OPNsenseDataUpdateCoordinator = data["coordinator"]
    tracker_interfaces = data[CONF_TRACKER_INTERFACES]
    tracker_mac_addresses = data[CONF_TRACKER_MAC_ADDRESSES]

    entity_registry = er.async_get(hass)
    existing_entities_list = [
        entity
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if entity.platform == DOMAIN
    ]
    existing_entities_set = {entity.unique_id for entity in existing_entities_list}

    entities = []
    devices_in_data = {}
    for device in coordinator.data:
        mac = device["mac"]
        if (
            tracker_interfaces
            and device.get("intf_description") not in tracker_interfaces
        ):
            continue
        if tracker_mac_addresses and mac not in tracker_mac_addresses:
            continue
        unique_id = format_mac(mac)
        devices_in_data[unique_id] = device
        if deleted_entity_id := entity_registry.async_get_entity_id(
            "device_tracker", DOMAIN, unique_id
        ):
            entity_entry = entity_registry.async_get(deleted_entity_id)
            if entity_entry and (
                entity_entry.config_entry_id != entry.entry_id
                or entity_entry.disabled_by is not None
            ):
                _LOGGER.debug(
                    "Removing orphaned entity %s before recreating",
                    deleted_entity_id,
                )
                entity_registry.async_remove(deleted_entity_id)

        entities.append(
            OPNsenseTrackerEntity(
                coordinator, device, tracker_interfaces, tracker_mac_addresses
            )
        )

    for entity_entry in existing_entities_list:
        if entity_entry.unique_id not in devices_in_data:
            mac = entity_entry.unique_id.replace(":", "").upper()
            mac_formatted = ":".join(
                mac[i : i + 2] for i in range(0, len(mac), 2)
            )
            should_track = True
            if tracker_mac_addresses and mac_formatted not in tracker_mac_addresses:
                should_track = False
            
            if should_track:
                device_data = {
                    "mac": mac_formatted,
                    "hostname": entity_entry.original_name or None,
                    "ip": None,
                    "intf_description": None,
                    "manufacturer": None,
                }
                entities.append(
                    OPNsenseTrackerEntity(
                        coordinator, device_data, tracker_interfaces, tracker_mac_addresses
                    )
                )

    if entities:
        async_add_entities(entities)

    first_check = True

    @callback
    def _async_check_devices() -> None:
        """Check for new/removed devices and update entities."""
        nonlocal first_check
        new_entities = []
        valid_macs = {
            format_mac(device["mac"])
            for device in coordinator.data
            if (
                not tracker_interfaces
                or device.get("intf_description") in tracker_interfaces
            )
            and (not tracker_mac_addresses or device["mac"] in tracker_mac_addresses)
        }

        entity_registry = er.async_get(hass)
        existing_entities_list = [
            entity
            for entity in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            if entity.platform == DOMAIN
        ]
        existing_entities_set = {entity.unique_id for entity in existing_entities_list}

        new_macs = valid_macs - existing_entities_set
        for device in coordinator.data:
            mac = device["mac"]
            unique_id = format_mac(mac)
            if unique_id in new_macs:
                if deleted_entity_id := entity_registry.async_get_entity_id(
                    "device_tracker", DOMAIN, unique_id
                ):
                    entity_entry = entity_registry.async_get(deleted_entity_id)
                    if entity_entry and (
                        entity_entry.config_entry_id != entry.entry_id
                        or entity_entry.disabled_by is not None
                    ):
                        _LOGGER.debug(
                            "Removing orphaned entity %s before recreating",
                            deleted_entity_id,
                        )
                        entity_registry.async_remove(deleted_entity_id)

                new_entities.append(
                    OPNsenseTrackerEntity(
                        coordinator, device, tracker_interfaces, tracker_mac_addresses
                    )
                )

        removed_entities = existing_entities_set - valid_macs
        if removed_entities and not first_check:
            for entity_entry in existing_entities_list:
                if entity_entry.unique_id in removed_entities:
                    _LOGGER.debug(
                        "Removing entity %s (MAC no longer tracked)",
                        entity_entry.entity_id,
                    )
                    entity_registry.async_remove(entity_entry.entity_id)

        if new_entities:
            _LOGGER.debug("Adding %d new device tracker entities", len(new_entities))
            async_add_entities(new_entities)

        first_check = False

    entry.async_on_unload(coordinator.async_add_listener(_async_check_devices))


class OPNsenseDeviceScanner(DeviceScanner):
    """This class queries a router running OPNsense (legacy)."""

    def __init__(
        self,
        client: diagnostics.InterfaceClient,
        interfaces: list[str],
        mac_addresses: list[str] | None = None,
    ) -> None:
        """Initialize the scanner."""
        self.last_results: dict[str, Any] = {}
        self.client = client
        self.interfaces = interfaces
        self.mac_addresses = mac_addresses or []

    def _get_mac_addrs(self, devices: list[DeviceDetails]) -> DeviceDetailsByMAC | dict:
        """Create dict with mac address keys from list of devices."""
        out_devices = {}
        for device in devices:
            mac = device["mac"]
            if self.interfaces and device["intf_description"] not in self.interfaces:
                continue
            if self.mac_addresses and mac not in self.mac_addresses:
                continue
            out_devices[mac] = device
        return out_devices

    def scan_devices(self) -> list[str]:
        """Scan for new devices and return a list with found device IDs."""
        self.update_info()
        return list(self.last_results)

    def get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        if device not in self.last_results:
            return None
        return self.last_results[device].get("hostname") or None

    def update_info(self) -> bool:
        """Ensure the information from the OPNsense router is up to date.

        Return boolean if scanning successful.
        """
        devices = self.client.get_arp()
        self.last_results = self._get_mac_addrs(devices)
        return True

    def get_extra_attributes(self, device: str) -> dict[Any, Any]:
        """Return the extra attrs of the given device."""
        if device not in self.last_results:
            return {}
        mfg = self.last_results[device].get("manufacturer")
        if not mfg:
            return {}
        return {"manufacturer": mfg}


class OPNsenseTrackerEntity(
    CoordinatorEntity[OPNsenseDataUpdateCoordinator], ScannerEntity
):
    """Represent a tracked device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OPNsenseDataUpdateCoordinator,
        device: dict[str, Any],
        tracker_interfaces: list[str],
        tracker_mac_addresses: list[str],
    ) -> None:
        """Initialize the tracker entity."""
        super().__init__(coordinator)
        self._device = device
        self._mac = device["mac"]
        self._config_entry_id = coordinator.config_entry.entry_id
        self._tracker_interfaces = tracker_interfaces
        self._tracker_mac_addresses = tracker_mac_addresses
        self._attr_unique_id = format_mac(self._mac)
        hostname = device.get("hostname")
        if hostname and hostname.strip():
            self._attr_name = hostname.strip()
        else:
            self._attr_name = format_mac(self._mac)
        self._attr_hostname = (
            hostname.strip() if hostname and hostname.strip() else None
        )
        self._attr_ip_address = device.get("ip")
        self._attr_mac_address = self._mac

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._should_track()

    def _should_track(self) -> bool:
        """Check if device should be tracked based on filters."""
        tracker_interfaces = self._tracker_interfaces
        tracker_mac_addresses = self._tracker_mac_addresses

        if self._config_entry_id and self.hass.data.get(OPNSENSE_DATA, {}).get(
            self._config_entry_id
        ):
            data = self.hass.data[OPNSENSE_DATA][self._config_entry_id]
            tracker_interfaces = data.get(CONF_TRACKER_INTERFACES, [])
            tracker_mac_addresses = data.get(CONF_TRACKER_MAC_ADDRESSES, [])

        if tracker_interfaces:
            if self._device.get("intf_description") not in tracker_interfaces:
                return False
        if tracker_mac_addresses:
            if self._mac not in tracker_mac_addresses:
                return False
        return True

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        if not self._should_track():
            return False
        # Check if device is in current coordinator data
        for device in self.coordinator.data:
            if device["mac"] == self._mac:
                return True
        return False

    @property
    def source_type(self) -> str:
        """Return the source type."""
        return "router"

    @callback
    def find_device_entry(self) -> None:
        """Return device entry.

        Override to prevent automatic linking to existing device registry entries.
        """
        return

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default."""
        return True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs: dict[str, Any] = {}
        if self._device.get("manufacturer"):
            attrs["manufacturer"] = self._device["manufacturer"]
        if self._device.get("ip"):
            attrs["ip"] = self._device["ip"]
        if self._device.get("intf_description"):
            attrs["interface"] = self._device["intf_description"]
        return attrs

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        for device in self.coordinator.data:
            if device["mac"] == self._mac:
                self._device = device
                hostname = device.get("hostname")
                if hostname and hostname.strip():
                    self._attr_name = hostname.strip()
                    self._attr_hostname = hostname.strip()
                else:
                    if not self._attr_name or self._attr_name == "Unknown":
                        self._attr_name = format_mac(self._mac)
                    self._attr_hostname = None
                if device.get("ip"):
                    self._attr_ip_address = device["ip"]
                break
        self.async_write_ha_state()
