"""Support for fetching WiFi associations through SNMP."""

import binascii
import logging
from typing import TYPE_CHECKING, override

import probatio
from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,
    Udp6TransportTarget,
    UdpTransportTarget,
    UsmUserData,
    bulk_walk_cmd,
    is_end_of_mib,
)

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
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
    SUBENTRY_TYPE_DEVICE_TRACKER,
)
from .coordinator import SnmpConfigEntry, SnmpDeviceTrackerCoordinator
from .util import RequestArgsType, async_create_request_cmd_args

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_BASEOID): cv.string,
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
        probatio.Inclusive(probatio.Secret(CONF_AUTH_KEY), "keys"): cv.string,
        probatio.Inclusive(probatio.Secret(CONF_PRIV_KEY), "keys"): cv.string,
    }
)


class SnmpScanner(DeviceScanner):
    """Queries any SNMP capable Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner after testing the target device."""

        community = config[CONF_COMMUNITY]
        baseoid = config[CONF_BASEOID]
        authkey = config.get(CONF_AUTH_KEY)
        authproto = DEFAULT_AUTH_PROTOCOL
        privkey = config.get(CONF_PRIV_KEY)
        privproto = DEFAULT_PRIV_PROTOCOL

        if authkey is not None or privkey is not None:
            if not authkey:
                authproto = "none"
            if not privkey:
                privproto = "none"

            self._auth_data = UsmUserData(
                community,
                authKey=authkey or None,
                privKey=privkey or None,
                authProtocol=authproto,
                privProtocol=privproto,
            )
        else:
            self._auth_data = CommunityData(
                community, mpModel=SNMP_VERSIONS[DEFAULT_VERSION]
            )

        self._target: UdpTransportTarget | Udp6TransportTarget
        self.request_args: RequestArgsType | None = None
        self.baseoid = baseoid
        self.last_results = []
        self.success_init = False

    @classmethod
    async def create(cls, config):
        """Test the target device before fully initializing."""
        host = config[CONF_HOST]

        try:
            # Try IPv4 first.
            target = await UdpTransportTarget.create(
                (host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
            )
        except PySnmpError:
            # Then try IPv6.
            try:
                target = Udp6TransportTarget(
                    (host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
                )
            except PySnmpError as err:
                _LOGGER.error("Invalid SNMP host: %s", err)
                return None
        instance = cls(config)
        instance._target = target

        return instance

    async def async_init(self, hass: HomeAssistant) -> None:
        """Check if the target device is reachable and readable."""
        self.request_args = await async_create_request_cmd_args(
            hass,
            self._auth_data,
            self._target,
            self.baseoid,
        )
        data = await self.async_get_snmp_data()
        self.success_init = data is not None

    @override
    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._async_update_info()
        return [client["mac"] for client in self.last_results if client.get("mac")]

    @override
    async def async_get_device_name(self, device: str) -> str | None:
        """Return the name of the given device or None if we don't know."""
        # We have no names
        return None

    @override
    async def async_get_extra_attributes(self, device: str) -> dict:
        """Return extra attributes of the given device."""
        for client in self.last_results:
            if client.get("mac") and device == client["mac"]:
                return {"mac": client["mac"]}
        return {}

    async def _async_update_info(self):
        """Ensure the information from the device is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        if not (data := await self.async_get_snmp_data()):
            return False

        self.last_results = data
        return True

    async def async_get_snmp_data(self):
        """Fetch MAC addresses from access point via SNMP."""
        devices = []
        if TYPE_CHECKING:
            assert self.request_args is not None

        engine, auth_data, target, context_data, object_type = self.request_args
        walker = bulk_walk_cmd(
            engine,
            auth_data,
            target,
            context_data,
            0,
            50,
            object_type,
            lexicographicMode=False,
        )
        async for errindication, errstatus, errindex, res in walker:
            if errindication:
                _LOGGER.error("SNMPLIB error: %s", errindication)
                return None
            if errstatus:
                _LOGGER.error(
                    "SNMP error: %s at %s",
                    errstatus.prettyPrint(),
                    (errindex and res[int(errindex) - 1][0]) or "?",
                )
                return None

            for _oid, value in res:
                if not is_end_of_mib(res):
                    try:
                        mac = binascii.hexlify(value.asOctets()).decode("utf-8")
                    except AttributeError:
                        continue
                    _LOGGER.debug("Found MAC address: %s", mac)
                    mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
                    devices.append({"mac": mac})
        return devices


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> SnmpScanner | None:
    """Validate the configuration and return an SNMP scanner."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_device_tracker",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        is_persistent=True,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml_device_tracker",
        translation_placeholders={"integration_title": "SNMP"},
    )

    scanner = await SnmpScanner.create(config[DEVICE_TRACKER_DOMAIN])
    if scanner is None:
        return None
    await scanner.async_init(hass)

    return scanner if scanner.success_init else None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SnmpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device trackers of the entry's subentries."""
    ent_reg = er.async_get(hass)

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_DEVICE_TRACKER):
        _async_setup_subentry(entry, subentry.subentry_id, ent_reg, async_add_entities)


@callback
def _async_setup_subentry(
    entry: SnmpConfigEntry,
    subentry_id: str,
    ent_reg: er.EntityRegistry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the tracker entities of a single subentry."""
    coordinator = entry.runtime_data.coordinators[subentry_id]

    # Ensure previously known MACs show up as 'not_home' instead of disappearing
    # if missing from the current poll.
    unique_id_prefix = f"{subentry_id}_"
    initial_macs = {
        reg_entry.unique_id.removeprefix(unique_id_prefix)
        for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if reg_entry.unique_id
        and reg_entry.unique_id.startswith(unique_id_prefix)
        and reg_entry.config_subentry_id == subentry_id
        and reg_entry.domain == DEVICE_TRACKER_DOMAIN
        and reg_entry.platform == DOMAIN
    }

    if initial_macs:
        async_add_entities(
            (SnmpTrackerEntity(coordinator, mac) for mac in initial_macs),
            config_subentry_id=subentry_id,
        )

    tracked_macs = set(initial_macs)

    @callback
    def _handle_coordinator_update() -> None:
        """Handle updated data from the coordinator."""
        if not coordinator.data:
            return

        new_entities: list[SnmpTrackerEntity] = []
        for mac in coordinator.data:
            if mac in tracked_macs:
                continue
            tracked_macs.add(mac)
            new_entities.append(SnmpTrackerEntity(coordinator, mac))

        if new_entities:
            async_add_entities(new_entities, config_subentry_id=subentry_id)

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    _handle_coordinator_update()


class SnmpTrackerEntity(CoordinatorEntity[SnmpDeviceTrackerCoordinator], ScannerEntity):
    """Represent an individual device tracked via SNMP."""

    def __init__(
        self,
        coordinator: SnmpDeviceTrackerCoordinator,
        mac: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.subentry_id}_{mac}"
        self._attr_mac_address = mac
        self._attr_name = mac
        self._attr_ip_address = coordinator.data.get(mac) if coordinator.data else None

    @property
    @override
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity.

        ScannerEntity derives the unique ID from the MAC address, which would
        collide between subentries tracking the same device.
        """
        return self._attr_unique_id

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan."""
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Update attribute so base class can use it."""
        assert self._attr_mac_address is not None
        self._attr_ip_address = (
            self.coordinator.data.get(self._attr_mac_address)
            if self.coordinator.data
            else None
        )
        super()._handle_coordinator_update()
