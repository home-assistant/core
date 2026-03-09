"""Support for fetching WiFi associations through SNMP.

This file implements the 'device_tracker' platform for the SNMP integration.

--- WHAT IS SNMP? ---
SNMP (Simple Network Management Protocol) is a standard "language" used by network 
devices (routers, switches, printers) to share information. Think of it as a 
giant, organized spreadsheet that lives inside your router.

--- KEY SNMP CONCEPTS USED HERE ---
1. OID (Object Identifier): This is like a phone number for a specific piece of 
   data. For example, ".1.3.6.1.2.1.1.5.0" might be the phone number to ask the 
   router for its name. OIDs are long strings of numbers.
2. Community String: In SNMP v1 and v2c, this is a simple "password" (usually 
   'public' or 'private') that allows you to read the data.
3. SNMP Walk: Instead of asking for one specific piece of data (a "GET"), a 
   "Walk" tells the router: "Starting from this OID, give me EVERYTHING you have 
   in this section." We use this to get a list of ALL connected MAC addresses.
4. Base OID: This is the starting point for our "Walk". We start at the OID that 
   represents the "List of Connected Devices".
"""

from __future__ import annotations

import binascii
from datetime import timedelta
import logging

# PySNMP is the library we use to speak the SNMP language.
from pysnmp.error import PySnmpError
from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData,       # Used for SNMP v1 and v2c (simple passwords)
    Udp6TransportTarget, # Used to connect to the router via IPv6
    UdpTransportTarget,  # Used to connect to the router via IPv4
    UsmUserData,         # Used for SNMP v3 (secure username/password)
    bulk_walk_cmd,       # The command to "Walk" through a list of data
    is_end_of_mib,       # A check to see if we reached the end of the list
)

# ScannerEntity is the Home Assistant blueprint for a network-scanning tracker.
from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    ScannerEntity,
)
# SOURCE_IMPORT is a flag telling us the data came from 'configuration.yaml'.
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType
# The Coordinator manages the schedule (e.g., "Ask the router every 10 seconds").
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

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
from .util import RequestArgsType, async_create_request_cmd_args

_LOGGER = logging.getLogger(__name__)

# We ask the router for a fresh list every 10 seconds.
SCAN_INTERVAL = timedelta(seconds=10)


async def async_get_scanner(hass: HomeAssistant, config: ConfigType) -> None:
    """Validate the configuration and trigger an import flow.
    
    This is the "Legacy Bridge". If Home Assistant sees an old 'device_tracker: snmp'
    entry in your YAML file, it calls this. Instead of starting the old-style 
    scanner, we trigger the "Config Flow" to migrate the settings into the 
    new UI-based database.
    """
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config[DEVICE_TRACKER_DOMAIN],
        )
    )
    # Returning None tells HA: "I didn't start a legacy scanner, someone else (the 
    # config flow) will handle it."
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SNMP device tracker from a Config Entry.
    
    This is called when the integration "starts up" (either at boot or after 
    using the Setup Wizard).
    """
    # 1. Pull the settings the user typed into the Setup Wizard.
    host = entry.data[CONF_HOST]
    community = entry.data.get(CONF_COMMUNITY, DEFAULT_COMMUNITY)
    baseoid = entry.data[CONF_BASEOID]
    authkey = entry.data.get(CONF_AUTH_KEY)
    privkey = entry.data.get(CONF_PRIV_KEY)

    # Protocols define HOW the data is encrypted or signed (mostly for SNMP v3).
    authproto = DEFAULT_AUTH_PROTOCOL
    privproto = DEFAULT_PRIV_PROTOCOL

    # 2. Prepare the Authentication ("Security Handshake").
    if authkey is not None or privkey is not None:
        # If the user provided keys, we use the Secure (v3) method.
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
        # Otherwise, we use the simple Password (v1/v2c) method.
        auth_data = CommunityData(community, mpModel=SNMP_VERSIONS[DEFAULT_VERSION])

    # 3. Create the Connection to the Router.
    try:
        # We try IPv4 (e.g., 192.168.1.1) first.
        target = await UdpTransportTarget.create(
            (host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT
        )
    except PySnmpError:
        try:
            # If IPv4 fails, we try IPv6.
            target = Udp6TransportTarget((host, DEFAULT_PORT), timeout=DEFAULT_TIMEOUT)
        except PySnmpError as err:
            _LOGGER.error("Invalid SNMP host: %s", err)
            return

    # 4. Prepare the final arguments (merging Auth + Target + OID).
    request_args = await async_create_request_cmd_args(
        hass,
        auth_data,
        target,
        baseoid,
    )

    # 5. The Coordinator is the "Heartbeat". It polls the router every 10s.
    coordinator = SnmpUpdateCoordinator(hass, request_args)
    # Perform the very first fetch right now so we have data immediately.
    await coordinator.async_config_entry_first_refresh()

    # We keep a list of MACs we already have an Entity for, so we don't create 
    # duplicates if we see the same phone twice.
    tracked_macs: set[str] = set()

    @callback
    def _handle_coordinator_update() -> None:
        """Handle updated data from the coordinator.
        
        This is a "Listener". Every time the heart beats (the coordinator polls),
        it calls this. If a brand new MAC address is found, we create a new 
        Entity for it on the fly.
        """
        new_entities = []
        if coordinator.data:
            for mac in coordinator.data:
                if mac not in tracked_macs:
                    tracked_macs.add(mac)
                    # Create the 'Person' (Entity) for this MAC address.
                    new_entities.append(SnmpTrackerEntity(coordinator, mac))
        if new_entities:
            # Tells Home Assistant: "Here are some new devices I found, please 
            # show them in the UI."
            async_add_entities(new_entities)

    # Tell the heart to notify us every time it beats.
    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))
    # Run once manually to catch everything found in the first poll.
    _handle_coordinator_update()


class SnmpUpdateCoordinator(DataUpdateCoordinator[list[str]]):
    """Class to manage fetching the list of MAC addresses from the router.
    
    The Coordinator pattern is the gold standard in HA. It ensures that if 10 
    different things need SNMP data, we only bother the router ONCE.
    """

    def __init__(self, hass: HomeAssistant, request_args: RequestArgsType) -> None:
        """Initialize the manager."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.request_args = request_args

    async def _async_update_data(self) -> list[str]:
        """Fetch the current list of MAC addresses via an SNMP Walk."""
        devices = []
        engine, auth_data, target, context_data, object_type = self.request_args
        
        # 'bulk_walk_cmd' performs a "Walk". It starts at our Base OID and finds 
        # every "child" OID underneath it, collecting their values (MAC addresses).
        walker = bulk_walk_cmd(
            engine,
            auth_data,
            target,
            context_data,
            0, # nonRepeaters
            50, # maxRepetitions (how many items to grab in one network packet)
            object_type,
            lexicographicMode=False,
        )
        async for errindication, errstatus, errindex, res in walker:
            # Network issue (e.g., router is off).
            if errindication:
                raise UpdateFailed(f"SNMPLIB error: {errindication}") from errindication
            # Logical issue (e.g., wrong password).
            if errstatus:
                err_msg = f"SNMP error: {errstatus.prettyPrint()} at {(errindex and res[int(errindex) - 1][0]) or '?'}"
                raise UpdateFailed(err_msg)

            for _oid, value in res:
                # Check if we've reached the end of the router's list.
                if not is_end_of_mib(res):
                    try:
                        # SNMP returns MAC addresses as 'Binary Bytes'. 
                        # We turn them into readable hex strings (e.g., 'aabbcc').
                        mac = binascii.hexlify(value.asOctets()).decode("utf-8")
                    except AttributeError:
                        # Some items in the walk might not be MACs; we skip them.
                        continue
                    # Format 'aabbccddeeff' into 'AA:BB:CC:DD:EE:FF'
                    mac = ":".join([mac[i : i + 2] for i in range(0, len(mac), 2)])
                    devices.append(mac)
        
        # This list of MACs is saved into 'self.data'.
        return devices


class SnmpTrackerEntity(CoordinatorEntity[SnmpUpdateCoordinator], ScannerEntity):
    """Represent an individual device tracked via SNMP.
    
    Each MAC address found gets its own instance of this class.
    """

    # We don't poll each entity; we let the Coordinator (theManager) do it for us.
    _attr_should_poll = False

    def __init__(self, coordinator: SnmpUpdateCoordinator, mac: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_mac_address = mac

    @property
    def is_connected(self) -> bool:
        """Return True if this MAC was seen in the latest scan.
        
        Home Assistant calls this to decide if the state should be 'home' or 
        'not_home'. We simply check if our MAC address is in the latest list 
        provided by the Coordinator.
        """
        if not self.coordinator.data:
            return False
        return self._attr_mac_address in self.coordinator.data
