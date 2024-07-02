"""Component to embed TP-Link smart home devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from aiohttp import ClientSession
from kasa import (
    AuthenticationError,
    Credentials,
    Device,
    DeviceConfig,
    Discover,
    KasaException,
)
from kasa.httpclient import get_cookie_jar
from kasa.iot import IotStrip

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
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_interval
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

type TPLinkConfigEntry = ConfigEntry[TPLinkData]

DISCOVERY_INTERVAL = timedelta(minutes=15)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


def create_async_tplink_clientsession(hass: HomeAssistant) -> ClientSession:
    """Return aiohttp clientsession with cookie jar configured."""
    return async_create_clientsession(
        hass, verify_ssl=False, cookie_jar=get_cookie_jar()
    )


@callback
def async_trigger_discovery(
    hass: HomeAssistant,
    discovered_devices: dict[str, Device],
) -> None:
    """Trigger config flows for discovered devices."""
    for formatted_mac, device in discovered_devices.items():
        discovery_flow.async_create_flow(
            hass,
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={
                CONF_ALIAS: device.alias or mac_alias(device.mac),
                CONF_HOST: device.host,
                CONF_MAC: formatted_mac,
                CONF_DEVICE_CONFIG: device.config.to_dict(
                    credentials_hash=device.credentials_hash,
                    exclude_credentials=True,
                ),
            },
        )


async def async_discover_devices(hass: HomeAssistant) -> dict[str, Device]:
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
    discovered_devices: dict[str, Device] = {}
    for device_list in await asyncio.gather(*tasks):
        for device in device_list.values():
            discovered_devices[dr.format_mac(device.mac)] = device
    return discovered_devices


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the TP-Link component."""
    hass.data.setdefault(DOMAIN, {})

    async def _async_discovery(*_: Any) -> None:
        if discovered := await async_discover_devices(hass):
            async_trigger_discovery(hass, discovered)

    hass.async_create_background_task(
        _async_discovery(), "tplink first discovery", eager_start=True
    )
    async_track_time_interval(
        hass, _async_discovery, DISCOVERY_INTERVAL, cancel_on_shutdown=True
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TPLinkConfigEntry) -> bool:
    """Set up TPLink from a config entry."""
    host: str = entry.data[CONF_HOST]
    credentials = await get_credentials(hass)

    config: DeviceConfig | None = None
    if config_dict := entry.data.get(CONF_DEVICE_CONFIG):
        try:
            config = DeviceConfig.from_dict(config_dict)
        except KasaException:
            _LOGGER.warning(
                "Invalid connection type dict for %s: %s", host, config_dict
            )

    if not config:
        config = DeviceConfig(host)
    else:
        config.host = host

    config.timeout = CONNECT_TIMEOUT
    if config.uses_http is True:
        config.http_client = create_async_tplink_clientsession(hass)
    if credentials:
        config.credentials = credentials
    try:
        device: Device = await Device.connect(config=config)
    except AuthenticationError as ex:
        raise ConfigEntryAuthFailed from ex
    except KasaException as ex:
        raise ConfigEntryNotReady from ex

    device_config_dict = device.config.to_dict(
        credentials_hash=device.credentials_hash, exclude_credentials=True
    )
    updates: dict[str, Any] = {}
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

    # The iot HS300 allows a limited number of concurrent requests and fetching the
    # emeter information requires separate ones so create child coordinators here.
    if isinstance(device, IotStrip):
        child_coordinators = [
            # The child coordinators only update energy data so we can
            # set a longer update interval to avoid flooding the device
            TPLinkDataUpdateCoordinator(hass, child, timedelta(seconds=60))
            for child in device.children
        ]

    entry.runtime_data = TPLinkData(parent_coordinator, child_coordinators)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TPLinkConfigEntry) -> bool:
    """Unload a config entry."""
    data = entry.runtime_data
    device = data.parent_coordinator.device
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await device.protocol.close()

    return unload_ok


def legacy_device_id(device: Device) -> str:
    """Convert the device id so it matches what was used in the original version."""
    device_id: str = device.device_id
    # Plugs are prefixed with the mac in python-kasa but not
    # in pyHS100 so we need to strip off the mac
    if "_" not in device_id:
        return device_id
    return device_id.split("_")[1]


def get_device_name(device: Device, parent: Device | None = None) -> str:
    """Get a name for the device. alias can be none on some devices."""
    if device.alias:
        return device.alias
    # Return the child device type with an index if there's more than one child device
    # of the same type. i.e. Devices like the ks240 with one child of each type
    # skip the suffix
    if parent:
        devices = [
            child.device_id
            for child in parent.children
            if child.device_type is device.device_type
        ]
        suffix = f" {devices.index(device.device_id) + 1}" if len(devices) > 1 else ""
        return f"{device.device_type.value.capitalize()}{suffix}"
    return f"Unnamed {device.model}"


async def get_credentials(hass: HomeAssistant) -> Credentials | None:
    """Retrieve the credentials from hass data."""
    if DOMAIN in hass.data and CONF_AUTHENTICATION in hass.data[DOMAIN]:
        auth = hass.data[DOMAIN][CONF_AUTHENTICATION]
        return Credentials(auth[CONF_USERNAME], auth[CONF_PASSWORD])

    return None


async def set_credentials(hass: HomeAssistant, username: str, password: str) -> None:
    """Save the credentials to HASS data."""
    hass.data.setdefault(DOMAIN, {})[CONF_AUTHENTICATION] = {
        CONF_USERNAME: username,
        CONF_PASSWORD: password,
    }


def mac_alias(mac: str) -> str:
    """Convert a MAC address to a short address for the UI."""
    return mac.replace(":", "")[-4:].upper()


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    version = config_entry.version
    minor_version = config_entry.minor_version

    _LOGGER.debug("Migrating from version %s.%s", version, minor_version)

    if version == 1 and minor_version < 3:
        # Previously entities on child devices added themselves to the parent
        # device and set their device id as identifiers along with mac
        # as a connection which creates a single device entry linked by all
        # identifiers. Now we create separate devices connected with via_device
        # so the identifier linkage must be removed otherwise the devices will
        # always be linked into one device.
        dev_reg = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id):
            new_identifiers: set[tuple[str, str]] | None = None
            if len(device.identifiers) > 1 and (
                mac := next(
                    iter(
                        [
                            conn[1]
                            for conn in device.connections
                            if conn[0] == dr.CONNECTION_NETWORK_MAC
                        ]
                    ),
                    None,
                )
            ):
                for identifier in device.identifiers:
                    # Previously only iot devices that use the MAC address as
                    # device_id had child devices so check for mac as the
                    # parent device.
                    if identifier[0] == DOMAIN and identifier[1].upper() == mac.upper():
                        new_identifiers = {identifier}
                        break
                if new_identifiers:
                    dev_reg.async_update_device(
                        device.id, new_identifiers=new_identifiers
                    )
                    _LOGGER.debug(
                        "Replaced identifiers for device %s (%s): %s with: %s",
                        device.name,
                        device.model,
                        device.identifiers,
                        new_identifiers,
                    )
                else:
                    # No match on mac so raise an error.
                    _LOGGER.error(
                        "Unable to replace identifiers for device %s (%s): %s",
                        device.name,
                        device.model,
                        device.identifiers,
                    )

        minor_version = 3
        hass.config_entries.async_update_entry(config_entry, minor_version=3)

        _LOGGER.debug("Migration to version %s.%s successful", version, minor_version)

    return True
