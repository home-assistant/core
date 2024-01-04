"""Component to embed TP-Link smart home devices."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Final, Optional

from kasa import (
    AuthenticationException,
    Credentials,
    DeviceConfig,
    Discover,
    SmartDevice,
    SmartDeviceException,
)

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ALIAS,
    CONF_AUTHENTICATION,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_USERNAME,
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
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_CONFIG,
    CONNECT_TIMEOUT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TPLinkDataUpdateCoordinator
from .models import TPLinkData

DISCOVERY_INTERVAL = timedelta(minutes=15)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

DATA_STORE: Final = "store"


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
                CONF_ALIAS: device.alias,
                CONF_HOST: device.host,
                CONF_MAC: formatted_mac,
                CONF_DEVICE_CONFIG: device.config.to_dict(
                    credentials_hash=device.credentials_hash
                ),
            },
        )


async def async_discover_devices(hass: HomeAssistant) -> dict[str, SmartDevice]:
    """Discover TPLink devices on configured network interfaces."""

    credentials = await get_credentials(hass)
    broadcast_addresses = await network.async_get_ipv4_broadcast_addresses(hass)
    tasks = [
        Discover.discover(
            target=str(address),
            discovery_timeout=DISCOVERY_TIMEOUT,
            timeout=CONNECT_TIMEOUT,
            credentials=credentials,
        )
        for address in broadcast_addresses
    ]
    discovered_devices: dict[str, SmartDevice] = {}
    for device_list in await asyncio.gather(*tasks):
        for device in device_list.values():
            discovered_devices[dr.format_mac(device.mac)] = device
    return discovered_devices


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TP-Link component."""
    hass.data.setdefault(DOMAIN, {})

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

    credentials = await get_credentials(hass)

    config = None
    if config_dict := entry.data.get(CONF_DEVICE_CONFIG):
        try:
            config = DeviceConfig.from_dict(config_dict)
        except SmartDeviceException:
            _LOGGER.warning(
                "Invalid connection type dict for %s: %s", host, config_dict
            )
    if not config:
        config = DeviceConfig(host)
    config.timeout = CONNECT_TIMEOUT
    if config.uses_http is True:
        config.http_client = create_async_httpx_client(hass, verify_ssl=False)
    if credentials:
        config.credentials = credentials
    try:
        device: SmartDevice = await SmartDevice.connect(config=config)
    except AuthenticationException as ex:
        raise ConfigEntryAuthFailed from ex
    except SmartDeviceException as ex:
        raise ConfigEntryNotReady from ex

    device_config_dict = device.config.to_dict(credentials_hash=device.credentials_hash)
    updates = {}
    if device_config_dict != config_dict:
        updates[CONF_DEVICE_CONFIG] = device_config_dict
    if entry.data.get(CONF_ALIAS) != device.alias:
        updates[CONF_ALIAS] = device.alias
    if entry.data.get(CONF_MODEL) != device.model:
        updates[CONF_MODEL] = device.model
    if updates:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                **updates,
            },
        )
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

    parent_coordinator = TPLinkDataUpdateCoordinator(hass, device, timedelta(seconds=5))
    child_coordinators: list[TPLinkDataUpdateCoordinator] = []

    if device.is_strip:
        child_coordinators = [
            # The child coordinators only update energy data so we can
            # set a longer update interval to avoid flooding the device
            TPLinkDataUpdateCoordinator(hass, child, timedelta(seconds=60))
            for child in device.children
        ]

    hass.data[DOMAIN][entry.entry_id] = TPLinkData(
        parent_coordinator, child_coordinators
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data: dict[str, Any] = hass.data[DOMAIN]
    data: TPLinkData = hass_data[entry.entry_id]
    device = data.parent_coordinator.device
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass_data.pop(entry.entry_id)
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


async def get_credentials(hass: HomeAssistant) -> Optional[Credentials]:
    """Retrieve the credentials from hass data."""
    if DOMAIN in hass.data and CONF_AUTHENTICATION in hass.data[DOMAIN]:
        auth = hass.data[DOMAIN][CONF_AUTHENTICATION]
        return Credentials(auth[CONF_USERNAME], auth[CONF_PASSWORD])

    return None


async def set_credentials(hass: HomeAssistant, username: str, password: str) -> None:
    """Save the credentials to HASS data."""
    auth = {
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
    }
    hass.data.setdefault(DOMAIN, {})[CONF_AUTHENTICATION] = auth
