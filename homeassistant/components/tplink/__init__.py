"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

import asyncio
import base64
from datetime import timedelta
from typing import Any, Optional

from kasa import (
    AuthenticationException,
    Credentials,
    SmartDevice,
    SmartDeviceException,
    TPLinkSmartHomeProtocol,
)
from kasa.discover import Discover

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STARTED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
)
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    PLATFORMS,
    TPLINK_CLOUD_CREDENTIALS_SYNC,
    TPLINK_CLOUD_PASSWORD,
    TPLINK_CLOUD_USERNAME,
)
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


def _decrypt(encrypted: str) -> str:
    """Decrypt a string."""
    # return TPLinkSmartHomeProtocol.decrypt(bytes.fromhex(encrypted))
    try:
        return TPLinkSmartHomeProtocol.decrypt(base64.b64decode(encrypted.encode()))
    except Exception:
        return ""


def _encrypt(plaintext: str) -> str:
    """Encrypt a string."""
    eb = TPLinkSmartHomeProtocol.encrypt(plaintext)[4:]
    # return str(eb.hex())
    return base64.b64encode(eb).decode()


def get_credentials(
    hass: HomeAssistant, entry: Optional[ConfigEntry] = None
) -> Credentials:
    """Return credentials from supplied config entry or other config entries set to sync credentials."""
    if (
        entry
        and entry.options.get(TPLINK_CLOUD_USERNAME)
        and entry.options.get(TPLINK_CLOUD_PASSWORD)
    ):
        return Credentials(
            _decrypt(entry.options[TPLINK_CLOUD_USERNAME]),
            _decrypt(entry.options[TPLINK_CLOUD_PASSWORD]),
        )
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        if (
            config_entry != entry
            and config_entry.options.get(TPLINK_CLOUD_CREDENTIALS_SYNC)
            and config_entry.options.get(TPLINK_CLOUD_USERNAME)
            and config_entry.options.get(TPLINK_CLOUD_PASSWORD)
        ):
            return Credentials(
                _decrypt(config_entry.options[TPLINK_CLOUD_USERNAME]),
                _decrypt(config_entry.options[TPLINK_CLOUD_PASSWORD]),
            )
    return Credentials()


def encrypt_credentials(optionsdata: dict[str, Any]) -> dict[str, Any]:
    """Encrypt username and password for storage."""
    if optionsdata.get(TPLINK_CLOUD_USERNAME):
        optionsdata[TPLINK_CLOUD_USERNAME] = _encrypt(
            optionsdata[TPLINK_CLOUD_USERNAME]
        )
    if optionsdata.get(TPLINK_CLOUD_PASSWORD):
        optionsdata[TPLINK_CLOUD_PASSWORD] = _encrypt(
            optionsdata[TPLINK_CLOUD_PASSWORD]
        )
    return optionsdata


async def async_discover_devices(hass: HomeAssistant) -> dict[str, SmartDevice]:
    """Discover TPLink devices on configured network interfaces."""
    broadcast_addresses = await network.async_get_ipv4_broadcast_addresses(hass)
    tasks = [
        Discover.discover(target=str(address), credentials=get_credentials(hass))
        for address in broadcast_addresses
    ]
    discovered_devices: dict[str, SmartDevice] = {}
    for device_list in await asyncio.gather(*tasks):
        for device in device_list.values():
            discovered_devices[dr.format_mac(device.mac)] = device
    return discovered_devices


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TP-Link component."""
    hass.data[DOMAIN] = {}

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
    if update_listener not in entry.update_listeners:
        entry.add_update_listener(update_listener)
    host = entry.data[CONF_HOST]
    try:
        device: SmartDevice = await Discover.discover_single(
            host, credentials=get_credentials(hass, entry)
        )
        # Fix device title if it was previously unauthenticated
        if entry.title == f"{device.host} {device.model}":
            entry.title = f"{device.alias} {device.model}"
    except AuthenticationException as auex:
        raise ConfigEntryAuthFailed from auex
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
    # sdb9696: Should await? from the docs: You don’t want to await this coroutine if it is called as part of the setup of a component, because it can cause a deadlock.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


config_entry_syncer_id: Optional[str] = None


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)

    global config_entry_syncer_id
    if (
        entry.options.get(TPLINK_CLOUD_CREDENTIALS_SYNC)
        and config_entry_syncer_id is None
    ):
        config_entry_syncer_id = entry.entry_id
        try:
            for config_entry in hass.config_entries.async_entries(DOMAIN):
                if entry != config_entry and config_entry.options.get(
                    TPLINK_CLOUD_CREDENTIALS_SYNC
                ):
                    if config_entry.options.get(
                        TPLINK_CLOUD_USERNAME
                    ) != entry.options.get(
                        TPLINK_CLOUD_USERNAME
                    ) or config_entry.options.get(
                        TPLINK_CLOUD_PASSWORD
                    ) != entry.options.get(
                        TPLINK_CLOUD_PASSWORD
                    ):
                        hass.config_entries.async_update_entry(
                            config_entry, options=dict(entry.options)
                        )
        finally:
            config_entry_syncer_id = None


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    device: SmartDevice = hass_data[entry.entry_id].device
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass_data.pop(entry.entry_id)

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
