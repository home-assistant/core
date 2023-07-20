"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from kasa import (
    AuthCredentials,
    SmartDevice,
    SmartDeviceException,
    TPLinkSmartHomeProtocol,
    UnauthenticatedDevice,
)
from kasa.discover import Discover

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
    storage,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import DATA_STORAGE, DATA_STORAGE_VERSION, DOMAIN, PLATFORMS
from .coordinator import TPLinkDataUpdateCoordinator

DISCOVERY_INTERVAL = timedelta(minutes=15)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: dict[str, SmartDevice],
) -> None:
    """Trigger config flows for discovered devices."""
    for formatted_mac, device in discovered_devices.items():
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                CONF_NAME: device.alias,
                CONF_HOST: device.host,
                CONF_MAC: formatted_mac,
            },
        )


def decrypt(encrypted: str) -> str:
    """Decrypt a string."""
    return TPLinkSmartHomeProtocol.decrypt(bytes.fromhex(encrypted))


def encrypt(plaintext: str) -> str:
    """Encrypt a string."""
    eb = TPLinkSmartHomeProtocol.encrypt(plaintext)[4:]
    return str(eb.hex())


def _get_auth_credentials(hass: HomeAssistant) -> AuthCredentials:
    return AuthCredentials(
        username=decrypt(hass.data[DOMAIN][DATA_STORAGE][CONF_USERNAME]),
        password=decrypt(hass.data[DOMAIN][DATA_STORAGE][CONF_PASSWORD]),
    )


async def async_discover_devices(hass: HomeAssistant) -> dict[str, SmartDevice]:
    """Discover TPLink devices on configured network interfaces."""

    broadcast_addresses = await network.async_get_ipv4_broadcast_addresses(hass)
    tasks = [
        Discover.discover(
            target=str(address), auth_credentials=_get_auth_credentials(hass)
        )
        for address in broadcast_addresses
    ]
    discovered_devices: dict[str, SmartDevice] = {}
    for device_list in await asyncio.gather(*tasks):
        for device in device_list.values():
            discovered_devices[dr.format_mac(device.mac)] = device
    return discovered_devices


async def async_update_store(hass: HomeAssistant) -> bool:
    """Update the data store."""
    store: storage.Store = storage.Store(
        hass, DATA_STORAGE_VERSION, DOMAIN, private=True
    )
    await store.async_save(data=hass.data[DOMAIN][DATA_STORAGE])
    return True


async def async_init_store(hass: HomeAssistant) -> bool:
    """Initialize the data store."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    store: storage.Store = storage.Store(
        hass, DATA_STORAGE_VERSION, DOMAIN, private=True
    )
    stored = await store.async_load()
    if stored is None:
        stored = {CONF_USERNAME: "", CONF_PASSWORD: ""}

    hass.data[DOMAIN][DATA_STORAGE] = stored
    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TP-Link component."""

    # hass.data[DOMAIN] = {}

    await async_init_store(hass)

    if discovered_devices := await async_discover_devices(hass):
        async_trigger_discovery(hass, discovered_devices)

    async def _async_discovery(*_: Any) -> None:
        if discovered := await async_discover_devices(hass):
            async_trigger_discovery(hass, discovered)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_discovery)
    async_track_time_interval(
        hass, _async_discovery, DISCOVERY_INTERVAL, cancel_on_shutdown=True
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TPLink from a config entry."""
    host = entry.data[CONF_HOST]
    try:
        device: SmartDevice = await Discover.discover_single(host)
    except SmartDeviceException as ex:
        raise ConfigEntryNotReady from ex

    found_mac = dr.format_mac(device.mac)
    if found_mac != entry.unique_id:
        # If the mac address of the device does not match the unique_id
        # of the config entry, it likely means the DHCP lease has expired
        # and the device has been assigned a new IP address. We need to
        # wait for the next discovery to find the device at its new address
        # and update the config entry so we do not mix up devices.
        raise ConfigEntryNotReady(
            f"Unexpected device found at {host}; expected {entry.unique_id}, found {found_mac}"
        )

    hass.data[DOMAIN][entry.entry_id] = TPLinkDataUpdateCoordinator(hass, device)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    device: SmartDevice = hass_data[entry.entry_id].device
    if not isinstance(device, UnauthenticatedDevice):
        if unload_ok := await hass.config_entries.async_unload_platforms(
            entry, PLATFORMS
        ):
            hass_data.pop(entry.entry_id)
    else:
        hass_data.pop(entry.entry_id)
        unload_ok = True

    await device.protocol.close()
    return unload_ok


def legacy_device_id(device: SmartDevice) -> str:
    """Convert the device id so it matches what was used in the original version."""
    device_id: str = device.device_id
    # Plugs are prefixed with the mac in python-kasa but not
    # in pyHS100 so we need to strip off the mac
    if "_" not in device_id:
        return device_id
    return device_id.split("_")[1]
