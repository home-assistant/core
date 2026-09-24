"""Mitsubishi Comfort integration for Home Assistant."""

import asyncio
import logging
from typing import Any

from mitsubishi_comfort import (
    DeviceInfo,
    IndoorUnit,
    KumoStation,
    MitsubishiCloudAccount,
)
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError

from homeassistant.components.dhcp import async_discovered_service_info
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ADDRESSES,
    CONF_CREDENTIALS,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_RESPONSE_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import MitsubishiComfortConfigEntry, MitsubishiComfortCoordinator
from .helpers import (
    async_create_missing_address_issue,
    async_reconcile_missing_address_issue,
    build_credentials,
    is_fully_credentialed,
)

_LOGGER = logging.getLogger(__name__)


def _make_device(
    info: DeviceInfo,
    serial: str,
    address: str,
    session,
) -> IndoorUnit | KumoStation:
    """Create the appropriate device instance from DeviceInfo."""
    cls = IndoorUnit if info.is_indoor_unit else KumoStation
    return cls(
        name=info.label,
        address=address,
        password_b64=info.password,
        crypto_serial_hex=info.crypto_serial,
        serial=serial,
        connect_timeout=DEFAULT_CONNECT_TIMEOUT,
        response_timeout=DEFAULT_RESPONSE_TIMEOUT,
        session=session,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Set up Mitsubishi Comfort from a config entry."""
    session = async_get_clientsession(hass)
    account = MitsubishiCloudAccount(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
    )

    # Replay cached per-device credentials so discover_devices() can skip the
    # slow, rate-limited Socket.IO password fetch. The config flow seeds
    # these; without them a second Socket.IO call right after the flow's own
    # is throttled to empty, leaving devices unconfigurable.
    cached_credentials: dict[str, dict[str, str]] = entry.data.get(CONF_CREDENTIALS, {})

    # The issue is not persistent and unload deletes it: if the cloud is
    # unreachable below, addressless devices would retry with no fix flow
    # offered. Reconcile from the stored data now; the fresh device list
    # refines it further down.
    async_reconcile_missing_address_issue(hass, entry)

    try:
        await account.login()
        devices = await account.discover_devices(cached_credentials=cached_credentials)
    except AuthenticationError as err:
        raise ConfigEntryError("Mitsubishi cloud authentication failed") from err
    except DeviceConnectionError as err:
        raise ConfigEntryNotReady("Cannot reach Mitsubishi cloud") from err

    if not devices:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_devices",
        )

    # The cloud provides each device's MAC but never its LAN IP. Register every
    # device with its MAC so the manifest's "registered_devices" DHCP matcher
    # tracks it; DHCP discovery then supplies the IP via async_step_dhcp.
    device_registry = dr.async_get(hass)
    owned_macs = {dr.format_mac(info.mac) for info in devices.values() if info.mac}
    for serial, info in devices.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, serial)},
            # Connections are globally indexed: registering an empty MAC would
            # merge every MAC-less device into one registry entry.
            connections=(
                {(dr.CONNECTION_NETWORK_MAC, info.mac)} if info.mac else set()
            ),
            manufacturer="Mitsubishi",
            name=info.label,
            serial_number=serial,
        )

    # Cache the freshly discovered credentials (password, cryptoSerial, MAC) so
    # later setups replay them; also drops entries for devices no longer present.
    credentials = build_credentials(devices)

    # Stored IPs are keyed by MAC; drop any for devices no longer on the account.
    # Addresses come from DHCP discovery (async_step_dhcp), the sighting cache
    # below, and the repair flow — the cloud never returns a device's LAN IP.
    stored: dict[str, str] = entry.data.get(CONF_ADDRESSES, {})
    addresses = {mac: ip for mac, ip in stored.items() if mac in owned_macs}

    # The dhcp component caches every sighting, including devices seen before
    # they were registered here — those never re-fire registered_devices
    # discovery, so look the cache up instead of waiting for a new sighting.
    # Stored addresses win: live discovery handles genuine IP changes.
    discovered = {
        dr.format_mac(info.macaddress): info.ip
        for info in async_discovered_service_info(hass)
    }
    addresses |= {
        mac: ip
        for mac, ip in discovered.items()
        if mac in owned_macs and mac not in addresses
    }

    data_updates: dict[str, Any] = {}
    if credentials != cached_credentials:
        data_updates[CONF_CREDENTIALS] = credentials
    if addresses != stored:
        data_updates[CONF_ADDRESSES] = addresses
    if data_updates:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, **data_updates}
        )

    coordinators: dict[str, MitsubishiComfortCoordinator] = {}
    no_address: list[str] = []
    incomplete: list[str] = []
    for serial, info in devices.items():
        if not is_fully_credentialed(info):
            incomplete.append(info.label)
            continue
        address = addresses.get(dr.format_mac(info.mac))
        if not address:
            no_address.append(info.label)
            continue
        _LOGGER.debug("Setting up %s at %s", info.label, address)
        device = _make_device(info, serial, address, session)
        coordinators[serial] = MitsubishiComfortCoordinator(
            hass, entry, device, info.mac
        )

    if incomplete:
        _LOGGER.debug(
            "The cloud returned incomplete local connection data for %d device(s): %s",
            len(incomplete),
            ", ".join(sorted(incomplete)),
        )
    # A device the cloud cannot locate stays unaddressable across restarts
    # until DHCP discovery reaches it or the user enters an IP in the repair
    # flow; raise a fixable repair issue while any device lacks an address and
    # clear it once they all have one.
    if no_address:
        async_create_missing_address_issue(hass, entry.entry_id)
    else:
        ir.async_delete_issue(hass, DOMAIN, f"missing_address_{entry.entry_id}")
    # The three buckets reconcile: set up + awaiting address + incomplete local
    # data equals the number of devices on the account.
    _LOGGER.debug(
        "Set up %d of %d device(s); %d awaiting a LAN address, %d with incomplete local data",
        len(coordinators),
        len(devices),
        len(no_address),
        len(incomplete),
    )

    await asyncio.gather(
        *(c.async_config_entry_first_refresh() for c in coordinators.values())
    )

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Only after a successful unload: a failed unload leaves the entry
        # active, so its addressless devices still need the repair.
        ir.async_delete_issue(hass, DOMAIN, f"missing_address_{entry.entry_id}")
        await asyncio.gather(
            *(c.device.close() for c in entry.runtime_data.values()),
            return_exceptions=True,
        )
    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant, entry: MitsubishiComfortConfigEntry
) -> None:
    """Remove a config entry's leftovers.

    Removal never calls async_unload_entry for an entry that failed setup, so
    the repair issue such a setup left behind is deleted here.
    """
    ir.async_delete_issue(hass, DOMAIN, f"missing_address_{entry.entry_id}")
