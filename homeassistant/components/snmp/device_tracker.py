"""Support for fetching WiFi associations through SNMP."""

from __future__ import annotations

import logging

from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
)

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AUTH_KEY,
    CONF_BASEOID,
    CONF_COMMUNITY,
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


async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> None:
    """Validate the configuration and trigger an import flow."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DEVICE_TRACKER_DOMAIN],
        )
    )


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
                    new_entities.append(SnmpTrackerEntity(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    _handle_coordinator_update()


class SnmpTrackerEntity(CoordinatorEntity[SnmpUpdateCoordinator], ScannerEntity):
    """Represent an individual device tracked via SNMP."""

    _attr_should_poll = False

    def __init__(self, coordinator: SnmpUpdateCoordinator, mac: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac

    @property
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan."""
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data
