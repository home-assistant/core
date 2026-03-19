"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import logging
from typing import Any

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
)

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.components.device_tracker.legacy import AsyncSeeCallback
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
    CONF_IMPORTED_BY,
    CONF_PRIV_KEY,
    DEFAULT_AUTH_PROTOCOL,
    DEFAULT_COMMUNITY,
    DEFAULT_PORT,
    DEFAULT_PRIV_PROTOCOL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERSION,
    DOMAIN,
    SNMP_VERSIONS,
)
from .coordinator import SnmpUpdateCoordinator
from .util import async_create_request_cmd_args

_LOGGER = logging.getLogger(__name__)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Trigger an import flow to migrate YAML config to a config entry."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SNMP device tracker from a Config Entry."""
    host = entry.data[CONF_HOST]
    community = entry.data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    baseoid = entry.data[CONF_BASEOID]
    authkey = entry.data.get(CONF_AUTH_KEY)
    privkey = entry.data.get(CONF_PRIV_KEY)

    authproto = DEFAULT_AUTH_PROTOCOL
    privproto = DEFAULT_PRIV_PROTOCOL

    if authkey is not None or privkey is not None:
        if not authkey:
            authproto = "none"
        if not privkey:
            privproto = "none"

        auth_data = UsmUserData(
            community,
            authKey=authkey or None,
            privKey=privkey or None,
            authProtocol=authproto,
            privProtocol=privproto,
        )
    else:
        auth_data = CommunityData(community, mpModel=SNMP_VERSIONS[DEFAULT_VERSION])

    try:
        target = await UdpTransportTarget.create(
            (host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
        )
    except PySnmpError:
        try:
            target = Udp6TransportTarget((host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT)
        except PySnmpError as err:
            _LOGGER.error("Invalid SNMP host: %s", err)
            return

    request_args = await async_create_request_cmd_args(
        hass,
        auth_data,
        target,
        baseoid,
    )

    coordinator = SnmpUpdateCoordinator(hass, entry, request_args)
    await coordinator.async_config_entry_first_refresh()

    tracked_macs: set[str] = set()

    @callback
    def _handle_coordinator_update() -> None:
        """Handle updated data from the coordinator."""
        new_entities = []
        if coordinator.data:
            for mac in coordinator.data:
                if mac not in tracked_macs:
                    tracked_macs.add(mac)
                    new_entities.append(SnmpTrackerEntity(coordinator, entry, mac))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    _handle_coordinator_update()


class SnmpTrackerEntity(CoordinatorEntity[SnmpUpdateCoordinator], ScannerEntity):
    """Represent an individual device tracked via SNMP."""

    _attr_should_poll = False

    def __init__(
        self, coordinator: SnmpUpdateCoordinator, entry: ConfigEntry, mac: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._entry = entry

    @property
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan."""
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity (just the MAC address)."""
        assert self._attr_mac_address is not None
        return self._attr_mac_address

    @property
    def name(self) -> str:
        """Return the name of the device (MAC address with underscores)."""
        # Format MAC address as entity name: 00:11:22:33:44:55 -> 00_11_22_33_44_55
        assert self._attr_mac_address is not None
        return self._attr_mac_address.replace(":", "_")

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if entity is enabled by default.

        Entities are enabled by default if they were imported from YAML configuration,
        to avoid breaking existing automations.
        """
        return CONF_IMPORTED_BY in self._entry.data

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the extra state attributes of the device.

        Include the location information from Home Assistant configuration
        to maintain compatibility with the old integration.
        """
        attributes: dict[str, Any] = {}

        # Add home location from Home Assistant configuration
        latitude = getattr(self.hass.config, "latitude", None)
        longitude = getattr(self.hass.config, "longitude", None)
        if latitude is not None:
            attributes["latitude"] = latitude
        if longitude is not None:
            attributes["longitude"] = longitude

        # GPS accuracy is always 0 for router-based detection
        attributes["gps_accuracy"] = 0

        return attributes
