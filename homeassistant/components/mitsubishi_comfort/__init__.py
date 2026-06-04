"""Mitsubishi Comfort integration for Home Assistant."""

import asyncio
import logging

from mitsubishi_comfort import (
    DeviceInfo,
    IndoorUnit,
    KumoStation,
    MitsubishiCloudAccount,
)
from mitsubishi_comfort.exceptions import AuthenticationError, DeviceConnectionError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ADDRESSES,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_RESPONSE_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import MitsubishiComfortConfigEntry, MitsubishiComfortCoordinator

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

    try:
        await account.login()
        devices = await account.discover_devices()
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
    owned_macs = {dr.format_mac(info.mac) for info in devices.values()}
    for serial, info in devices.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, serial)},
            connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(info.mac))},
            manufacturer="Mitsubishi",
            name=info.label,
            serial_number=serial,
        )

    # Resolved IPs are stored keyed by MAC. Drop any for devices that are no
    # longer on the account.
    stored: dict[str, str] = entry.data.get(CONF_ADDRESSES, {})
    addresses = {mac: ip for mac, ip in stored.items() if mac in owned_macs}
    if addresses != stored:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ADDRESSES: addresses}
        )

    coordinators: dict[str, MitsubishiComfortCoordinator] = {}
    for serial, info in devices.items():
        address = addresses.get(dr.format_mac(info.mac))
        if not address or not info.password or not info.crypto_serial:
            # No LAN address yet: the device is registered, so DHCP discovery
            # supplies its IP and reloads the entry to add it.
            _LOGGER.debug("Device %s has no known LAN address yet", info.label)
            continue
        device = _make_device(info, serial, address, session)
        coordinators[serial] = MitsubishiComfortCoordinator(
            hass, entry, device, info.mac
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
        await asyncio.gather(
            *(c.device.close() for c in entry.runtime_data.values()),
            return_exceptions=True,
        )
    return unload_ok
