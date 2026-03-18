"""Component to embed TP-Link smart home devices."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import timedelta
import logging
from typing import Any, cast

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

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import (
    CONF_ALIAS,
    CONF_AUTHENTICATION,
    CONF_DEVICE,
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_PORT,
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
    CONF_AES_KEYS,
    CONF_CAMERA_CREDENTIALS,
    CONF_CONFIG_ENTRY_MINOR_VERSION,
    CONF_CONNECTION_PARAMETERS,
    CONF_CREDENTIALS_HASH,
    CONF_DEVICE_CONFIG,
    CONF_LIVE_VIEW,
    CONF_USES_HTTP,
    CONNECT_TIMEOUT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import TPLinkConfigEntry, TPLinkData, TPLinkDataUpdateCoordinator

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
                CONF_DEVICE: device,
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
    entry_credentials_hash = entry.data.get(CONF_CREDENTIALS_HASH)
    entry_use_http = entry.data.get(CONF_USES_HTTP, False)
    entry_aes_keys = entry.data.get(CONF_AES_KEYS)
    port_override = entry.data.get(CONF_PORT)

    conn_params: Device.ConnectionParameters | None = None
    if conn_params_dict := entry.data.get(CONF_CONNECTION_PARAMETERS):
        try:
            conn_params = Device.ConnectionParameters.from_dict(conn_params_dict)
        except (KasaException, TypeError, ValueError, LookupError):
            _LOGGER.warning(
                "Invalid connection parameters dict for %s: %s", host, conn_params_dict
            )

    client = create_async_tplink_clientsession(hass) if entry_use_http else None
    config = DeviceConfig(
        host,
        timeout=CONNECT_TIMEOUT,
        http_client=client,
        aes_keys=entry_aes_keys,
        port_override=port_override,
    )
    if conn_params:
        config.connection_type = conn_params
    # If we have in memory credentials use them otherwise check for credentials_hash
    if credentials:
        config.credentials = credentials
    elif entry_credentials_hash:
        config.credentials_hash = entry_credentials_hash

    try:
        device: Device = await Device.connect(config=config)
    except AuthenticationError as ex:
        # If the stored credentials_hash was used but doesn't work remove it
        if not credentials and entry_credentials_hash:
            data = {k: v for k, v in entry.data.items() if k != CONF_CREDENTIALS_HASH}
            hass.config_entries.async_update_entry(entry, data=data)
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="device_authentication",
            translation_placeholders={
                "func": "connect",
                "exc": str(ex),
            },
        ) from ex
    except KasaException as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_error",
            translation_placeholders={
                "func": "connect",
                "exc": str(ex),
            },
        ) from ex

    device_credentials_hash = device.credentials_hash

    # We not need to update the connection parameters or the use_http here
    # because if they were wrong we would have failed to connect.
    # Discovery will update those if necessary.
    updates: dict[str, Any] = {}
    if device_credentials_hash and device_credentials_hash != entry_credentials_hash:
        updates[CONF_CREDENTIALS_HASH] = device_credentials_hash
    if entry_aes_keys != device.config.aes_keys:
        updates[CONF_AES_KEYS] = device.config.aes_keys
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
            translation_domain=DOMAIN,
            translation_key="unexpected_device",
            translation_placeholders={
                "host": host,
                # all entries have a unique id
                "expected": cast(str, entry.unique_id),
                "found": found_mac,
            },
        )

    parent_coordinator = TPLinkDataUpdateCoordinator(
        hass, device, timedelta(seconds=5), entry
    )

    camera_creds: Credentials | None = None
    if camera_creds_dict := entry.data.get(CONF_CAMERA_CREDENTIALS):
        camera_creds = Credentials(
            camera_creds_dict[CONF_USERNAME], camera_creds_dict[CONF_PASSWORD]
        )
    live_view = entry.data.get(CONF_LIVE_VIEW)

    entry.runtime_data = TPLinkData(parent_coordinator, camera_creds, live_view)
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


def get_device_name(device: Device, parent: Device | None = None) -> str | None:
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
    return None


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


def _mac_connection_or_none(device: dr.DeviceEntry) -> str | None:
    return next(
        (
            conn
            for type_, conn in device.connections
            if type_ == dr.CONNECTION_NETWORK_MAC
        ),
        None,
    )


def _device_id_is_mac_or_none(mac: str, device_ids: Iterable[str]) -> str | None:
    # Previously only iot devices had child devices and iot devices use
    # the upper and lcase MAC addresses as device_id so match on case
    # insensitive mac address as the parent device.
    upper_mac = mac.upper()
    return next(
        (device_id for device_id in device_ids if device_id.upper() == upper_mac),
        None,
    )


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: TPLinkConfigEntry
) -> bool:
    """Migrate old entry."""
    entry_version = config_entry.version
    entry_minor_version = config_entry.minor_version
    # having a condition to check for the current version allows
    # tests to be written per migration step.
    config_flow_minor_version = CONF_CONFIG_ENTRY_MINOR_VERSION

    new_minor_version = 3
    if (
        entry_version == 1
        and entry_minor_version < new_minor_version <= config_flow_minor_version
    ):
        _LOGGER.debug(
            "Migrating from version %s.%s", entry_version, entry_minor_version
        )
        # Previously entities on child devices added themselves to the parent
        # device and set their device id as identifiers along with mac
        # as a connection which creates a single device entry linked by all
        # identifiers. Now we create separate devices connected with via_device
        # so the identifier linkage must be removed otherwise the devices will
        # always be linked into one device.
        dev_reg = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id):
            original_identifiers = device.identifiers
            # Get only the tplink identifier, could be tapo or other integrations.
            tplink_identifiers = [
                ident[1] for ident in original_identifiers if ident[0] == DOMAIN
            ]
            # Nothing to fix if there's only one identifier. mac connection
            # should never be none but if it is there's no problem.
            if len(tplink_identifiers) <= 1 or not (
                mac := _mac_connection_or_none(device)
            ):
                continue
            if not (
                tplink_parent_device_id := _device_id_is_mac_or_none(
                    mac, tplink_identifiers
                )
            ):
                # No match on mac so raise an error.
                _LOGGER.error(
                    "Unable to replace identifiers for device %s (%s): %s",
                    device.name,
                    device.model,
                    device.identifiers,
                )
                continue
            # Retain any identifiers for other domains
            new_identifiers = {
                ident for ident in device.identifiers if ident[0] != DOMAIN
            }
            new_identifiers.add((DOMAIN, tplink_parent_device_id))
            dev_reg.async_update_device(device.id, new_identifiers=new_identifiers)
            _LOGGER.debug(
                "Replaced identifiers for device %s (%s): %s with: %s",
                device.name,
                device.model,
                original_identifiers,
                new_identifiers,
            )

        hass.config_entries.async_update_entry(
            config_entry, minor_version=new_minor_version
        )

        _LOGGER.debug(
            "Migration to version %s.%s complete", entry_version, new_minor_version
        )

    new_minor_version = 4
    if (
        entry_version == 1
        and entry_minor_version < new_minor_version <= config_flow_minor_version
    ):
        # credentials_hash stored in the device_config should be moved to data.
        updates: dict[str, Any] = {}
        if config_dict := config_entry.data.get(CONF_DEVICE_CONFIG):
            assert isinstance(config_dict, dict)
            if credentials_hash := config_dict.pop(CONF_CREDENTIALS_HASH, None):
                updates[CONF_CREDENTIALS_HASH] = credentials_hash
                updates[CONF_DEVICE_CONFIG] = config_dict
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **config_entry.data,
                **updates,
            },
            minor_version=new_minor_version,
        )
        _LOGGER.debug(
            "Migration to version %s.%s complete", entry_version, new_minor_version
        )

    new_minor_version = 5
    if (
        entry_version == 1
        and entry_minor_version < new_minor_version <= config_flow_minor_version
    ):
        # complete device config no longer to be stored, only required
        # attributes like connection parameters and aes_keys
        updates = {}
        entry_data = {
            k: v for k, v in config_entry.data.items() if k != CONF_DEVICE_CONFIG
        }
        if config_dict := config_entry.data.get(CONF_DEVICE_CONFIG):
            assert isinstance(config_dict, dict)
            if connection_parameters := config_dict.get("connection_type"):
                updates[CONF_CONNECTION_PARAMETERS] = connection_parameters
            if (use_http := config_dict.get(CONF_USES_HTTP)) is not None:
                updates[CONF_USES_HTTP] = use_http
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                **entry_data,
                **updates,
            },
            minor_version=new_minor_version,
        )
        _LOGGER.debug(
            "Migration to version %s.%s complete", entry_version, new_minor_version
        )
    return True
