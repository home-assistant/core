"""Support for tracking for OPNsense devices."""

from collections.abc import MutableMapping
import contextlib
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_DEVICE_TRACKER_CONSIDER_HOME,
    CONF_DEVICE_TRACKER_ENABLED,
    CONF_DEVICES,
    DEFAULT_DEVICE_TRACKER_CONSIDER_HOME,
    DEFAULT_DEVICE_TRACKER_ENABLED,
    DEVICE_TRACKER_COORDINATOR,
    DOMAIN,
    SHOULD_RELOAD,
    TRACKED_MACS,
)
from .coordinator import OPNsenseDataUpdateCoordinator
from .entity import OPNsenseBaseEntity
from .helpers import dict_get

_LOGGER: logging.Logger = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OPNsense component."""

    dev_reg = dr.async_get(hass)

    previous_mac_addresses: list = config_entry.data.get(TRACKED_MACS, [])
    coordinator: OPNsenseDataUpdateCoordinator = getattr(
        config_entry.runtime_data, DEVICE_TRACKER_COORDINATOR
    )
    state = coordinator.data
    enabled_default = False
    entities: list = []
    mac_addresses: list = []

    arp_entries = dict_get(state, "arp_table")
    if not isinstance(arp_entries, list):
        arp_entries = []
    configured_mac_addresses = config_entry.options.get(CONF_DEVICES, [])
    device_tracker_enabled = config_entry.options.get(
        CONF_DEVICE_TRACKER_ENABLED, DEFAULT_DEVICE_TRACKER_ENABLED
    )
    devices: list[dict[str, Any]] = []
    mac_addresses = []

    # Use configured MAC addresses if set up, otherwise create an entity per ARP entry.
    if configured_mac_addresses and device_tracker_enabled:
        _LOGGER.debug(
            "[device_tracker async_setup_entry] configured_mac_addresses: %s",
            configured_mac_addresses,
        )
        enabled_default = True
        mac_addresses = configured_mac_addresses.copy()
        devices.extend(
            _build_device(mac_address, _find_arp_entry(arp_entries, mac_address))
            for mac_address in mac_addresses
        )
    elif device_tracker_enabled:
        for arp_entry in arp_entries:
            if not isinstance(arp_entry, MutableMapping):
                continue
            mac_address = arp_entry.get("mac")
            if mac_address and mac_address not in mac_addresses:
                mac_addresses.append(mac_address)
                devices.append(_build_device(mac_address, arp_entry))

    for device in devices:
        mac = device.get("mac")
        if not isinstance(mac, str):
            continue
        entity = OPNsenseScannerEntity(
            config_entry=config_entry,
            coordinator=coordinator,
            enabled_default=enabled_default,
            mac=mac,
            mac_vendor=device.get("manufacturer", None),
            hostname=device.get("hostname", None),
        )
        entities.append(entity)
    # Get the MACs that need to be removed and remove their devices
    for mac_address in list(set(previous_mac_addresses) - set(mac_addresses)):
        rem_device = dev_reg.async_get_device(
            connections={(CONNECTION_NETWORK_MAC, mac_address)}
        )
        if rem_device:
            dev_reg.async_remove_device(rem_device.id)

    if set(mac_addresses) != set(previous_mac_addresses):
        setattr(config_entry.runtime_data, SHOULD_RELOAD, False)
        new_data = config_entry.data.copy()
        new_data[TRACKED_MACS] = mac_addresses.copy()
        hass.config_entries.async_update_entry(config_entry, data=new_data)

    _LOGGER.debug("[device_tracker async_setup_entry] entities: %s", len(entities))
    async_add_entities(entities)


def _find_arp_entry(
    arp_entries: list[Any], mac_address: str
) -> MutableMapping[str, Any] | None:
    """Find the ARP entry for a MAC address."""
    for arp_entry in arp_entries:
        if not isinstance(arp_entry, MutableMapping):
            continue
        if arp_entry.get("mac", "") == mac_address:
            return arp_entry
    return None


def _build_device(
    mac_address: str, arp_entry: MutableMapping[str, Any] | None
) -> dict[str, Any]:
    """Build tracked device metadata from an ARP entry."""
    device: dict[str, Any] = {"mac": mac_address}
    if arp_entry is None:
        return device

    for attr in ("hostname", "manufacturer"):
        value = arp_entry.get(attr)
        if value:
            device[attr] = value
    return device


class OPNsenseScannerEntity(OPNsenseBaseEntity, ScannerEntity, RestoreEntity):
    """Represent a scanned device."""

    _attr_translation_key = "device_tracker"

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: OPNsenseDataUpdateCoordinator,
        enabled_default: bool,
        mac: str,
        mac_vendor: str | None,
        hostname: str | None,
    ) -> None:
        """Set up the OPNsense scanner entity."""
        super().__init__(config_entry, coordinator, unique_id_suffix=f"mac_{mac}")
        self._mac_vendor: str | None = mac_vendor
        self._attr_name: str | None = f"{self.opnsense_device_name} {hostname or mac}"
        self._last_known_ip: str | None = None
        self._last_known_hostname: str | None = None
        self._is_connected: bool = False
        self._last_known_connected_time: datetime | None = None
        self._attr_entity_registry_enabled_default: bool = enabled_default
        self._attr_hostname: str | None = hostname
        self._attr_ip_address: str | None = None
        self._attr_mac_address: str | None = mac
        self._attr_source_type: SourceType = SourceType.ROUTER

    @property
    def source_type(self) -> SourceType:
        """Return the tracker source type."""
        return self._attr_source_type

    @property
    def is_connected(self) -> bool:
        """Return if the tracker is connected."""
        return self._is_connected

    @property
    def ip_address(self) -> str | None:
        """Return the IP address."""
        return self._attr_ip_address

    @property
    def mac_address(self) -> str | None:
        """Return the MAC address."""
        return self._attr_mac_address

    @property
    def hostname(self) -> str | None:
        """Return the hostname."""
        return self._attr_hostname

    @property
    def unique_id(self) -> str | None:
        """Return the unique id."""
        return self._attr_unique_id

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity registry is enabled by default."""
        return self._attr_entity_registry_enabled_default

    @staticmethod
    def _get_entry_value(entry: MutableMapping[str, Any], key: str) -> str | None:
        """Return a string value from an ARP entry."""
        value = entry.get(key)
        if not isinstance(value, str):
            return None
        if key == "hostname":
            value = value.strip("?")
        return value or None

    def _update_cached_values(self, entry: MutableMapping[str, Any]) -> None:
        """Update cached hostname and IP values."""
        self._attr_ip_address = self._get_entry_value(entry, "ip")
        if self._attr_ip_address:
            self._last_known_ip = self._attr_ip_address

        self._attr_hostname = self._get_entry_value(entry, "hostname")
        if self._attr_hostname:
            self._last_known_hostname = self._attr_hostname

    def _update_connection_state(
        self, entry: MutableMapping[str, Any], state: MutableMapping[str, Any]
    ) -> None:
        """Update connection tracking state."""
        if not entry or entry.get("expired", False):
            self._is_connected = False
            device_tracker_consider_home = self.config_entry.options.get(
                CONF_DEVICE_TRACKER_CONSIDER_HOME, DEFAULT_DEVICE_TRACKER_CONSIDER_HOME
            )
            if device_tracker_consider_home > 0 and isinstance(
                self._last_known_connected_time, datetime
            ):
                elapsed: timedelta = (
                    datetime.now().astimezone() - self._last_known_connected_time
                )
                if elapsed.total_seconds() < device_tracker_consider_home:
                    self._is_connected = True
            return

        update_time = state.get("update_time")
        if isinstance(update_time, float):
            self._last_known_connected_time = datetime.fromtimestamp(
                int(update_time),
                tz=timezone(datetime.now().astimezone().utcoffset() or timedelta()),
            )
        self._is_connected = True

    def _update_entry_attributes(self, entry: MutableMapping[str, Any]) -> None:
        """Update state attributes from the current ARP entry."""
        ha_to_opnsense: dict[str, str] = {
            "interface": "intf_description",
            "expires": "expires",
            "type": "type",
        }
        for prop_name, opnsense_name in ha_to_opnsense.items():
            prop = entry.get(opnsense_name)
            if not prop:
                continue
            if prop_name == "expires":
                if not isinstance(prop, (int, float)):
                    continue
                self._attr_extra_state_attributes[prop_name] = (
                    "Never"
                    if prop == -1
                    else datetime.now().astimezone() + timedelta(seconds=prop)
                )
                continue
            self._attr_extra_state_attributes[prop_name] = prop

    @callback
    def _handle_coordinator_update(self) -> None:
        raw_state: object = self.coordinator.data
        if not isinstance(raw_state, MutableMapping):
            self._available = False
            self.async_write_ha_state()
            return
        state = raw_state
        arp_table = dict_get(state, "arp_table")
        if not isinstance(arp_table, list):
            self._available = False
            self.async_write_ha_state()
            return
        self._available = True
        entry: MutableMapping[str, Any] | None = None
        for arp_entry in arp_table:
            if not isinstance(arp_entry, MutableMapping):
                continue
            if arp_entry.get("mac", "").lower() == self._attr_mac_address:
                entry = arp_entry
                break
        if not entry:
            entry = {}
        if isinstance(entry, MutableMapping):
            self._update_cached_values(entry)
            self._update_connection_state(entry, state)
            self._update_entry_attributes(entry)

        if self._attr_hostname is None and self._last_known_hostname:
            self._attr_extra_state_attributes["last_known_hostname"] = (
                self._last_known_hostname
            )
        else:
            self._attr_extra_state_attributes.pop("last_known_hostname", None)

        if self._attr_ip_address is None and self._last_known_ip:
            self._attr_extra_state_attributes["last_known_ip"] = self._last_known_ip
        else:
            self._attr_extra_state_attributes.pop("last_known_ip", None)

        if self._last_known_connected_time is not None:
            self._attr_extra_state_attributes["last_known_connected_time"] = (
                self._last_known_connected_time
            )

        self.async_write_ha_state()

    @property  # type: ignore[misc] # overriding final from ScannerEntity
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self.mac_address or "")},
            default_manufacturer=self._mac_vendor or "",
            default_name=self.name if isinstance(self.name, str) else "",
            via_device=(DOMAIN, self._device_unique_id),
        )

    async def _restore_last_state(self) -> None:
        last_state = await self.async_get_last_state()
        if last_state is None or last_state.attributes is None:
            return

        state = last_state.attributes

        self._last_known_hostname = state.get("last_known_hostname", None)
        self._last_known_ip = state.get("last_known_ip", None)

        try:
            for attr in ("interface", "expires", "type"):
                value = state.get(attr, None)
                if value:
                    self._attr_extra_state_attributes[attr] = value
        except TypeError, KeyError, AttributeError:
            pass

        lkct = state.get("last_known_connected_time", None)
        if isinstance(lkct, datetime):
            self._attr_extra_state_attributes["last_known_connected_time"] = lkct
        elif isinstance(lkct, str):
            with contextlib.suppress(ValueError):
                self._attr_extra_state_attributes["last_known_connected_time"] = (
                    datetime.fromisoformat(lkct)
                )

    async def async_added_to_hass(self) -> None:
        """Commands to run after entity is created."""
        await self._restore_last_state()
        await super().async_added_to_hass()
