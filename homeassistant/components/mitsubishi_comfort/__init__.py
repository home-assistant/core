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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

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
    session,
) -> IndoorUnit | KumoStation:
    """Create the appropriate device instance from DeviceInfo."""
    cls = IndoorUnit if info.is_indoor_unit else KumoStation
    return cls(
        name=info.label,
        address=info.address,
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

    # The cloud supplies each device's password, crypto serial, and MAC, but not
    # its LAN IP. Resolve the IP from the DHCP-discovered address cache (keyed by
    # MAC) and register every owned MAC so async_step_dhcp knows which addresses
    # belong to this entry.
    stored: dict[str, str] = entry.data.get(CONF_ADDRESSES, {})
    # Keep an entry for every owned MAC (defaulting to ""), dropping MACs for
    # devices no longer on the account.
    addresses = {format_mac(info.mac): "" for info in devices.values()}
    addresses.update({mac: ip for mac, ip in stored.items() if mac in addresses})
    if addresses != stored:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_ADDRESSES: addresses}
        )

    coordinators: dict[str, MitsubishiComfortCoordinator] = {}
    for serial, info in devices.items():
        info.address = addresses.get(format_mac(info.mac)) or info.address
        if not info.address or not info.password or not info.crypto_serial:
            _LOGGER.debug(
                "Device %s has no known LAN address yet; it will be added once "
                "discovered on the network",
                info.label,
            )
            continue
        device = _make_device(info, serial, session)
        coordinators[serial] = MitsubishiComfortCoordinator(
            hass, entry, device, info.mac
        )

    if not coordinators:
        # No device has a usable LAN address yet. Raise so Home Assistant retries
        # with backoff; DHCP discovery will fill in addresses and reload the entry.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="no_devices_reachable",
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
