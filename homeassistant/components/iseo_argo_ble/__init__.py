"""ISEO Argo BLE Lock — Home Assistant integration."""

import asyncio
from dataclasses import dataclass
import logging
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ec import SECP224R1, derive_private_key
from iseo_argo_ble import IseoClient

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import (
    ACCESS_LOG_UNLOAD_TIMEOUT,
    CONF_PRIV_SCALAR,
    DEFAULT_USER_SUBTYPE,
    DOMAIN,
    PLATFORMS,
    SERVICE_READ_ACCESS_LOG,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class IseoData:
    """Runtime data for an ISEO config entry."""

    client: IseoClient
    # A destructive access-log read in flight, if any. Unloading waits for it:
    # the lock has already marked those entries read, so tearing the event
    # entity down first would lose them.
    access_log_read: asyncio.Task[None] | None = None
    # Whether the access-log event entity is listening. Reading the log
    # destroys it on the lock, so it must not be read with nobody to report
    # to — a user can disable the event entity and leave the lock enabled.
    access_log_consumer: bool = False


type IseoConfigEntry = ConfigEntry[IseoData]

# Entries drained from a lock but not yet reported, by entry id. Survives the
# entry so a read that finished after the event entity went away — an unload
# that outran the wait, for one — is replayed instead of lost: the lock has
# already marked those entries read and will never offer them again.
PENDING_LOG_ENTRIES: HassKey[dict[str, list[tuple[str, dict[str, Any]]]]] = HassKey(
    f"{DOMAIN}_pending_log_entries"
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions.

    Registered here rather than with the platform so the action exists even
    while the lock is unreachable, and automations using it stay valid.
    """
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_READ_ACCESS_LOG,
        entity_domain=LOCK_DOMAIN,
        schema=None,
        func="async_read_access_log",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Set up ISEO Argo BLE Lock from a config entry."""
    address = entry.data[CONF_ADDRESS]
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"address": address},
        )

    priv_int = int(entry.data[CONF_PRIV_SCALAR], 16)
    priv = await hass.async_add_executor_job(derive_private_key, priv_int, SECP224R1())
    uuid_bytes = bytes.fromhex(entry.data[CONF_UUID])

    client = IseoClient(
        address=address,
        uuid_bytes=uuid_bytes,
        identity_priv=priv,
        subtype=DEFAULT_USER_SUBTYPE,
        ble_device=ble_device,
    )

    entry.runtime_data = IseoData(client=client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Unload a config entry."""
    # Let a destructive access-log read finish first. Its entries are already
    # marked read on the lock, and unloading the platforms concurrently would
    # disconnect the event entity before they are delivered — losing them for
    # good. Bounded, so a wedged read cannot block the unload forever.
    if (read := entry.runtime_data.access_log_read) is not None and not read.done():
        try:
            async with asyncio.timeout(ACCESS_LOG_UNLOAD_TIMEOUT):
                await asyncio.shield(read)
        except TimeoutError, HomeAssistantError:
            _LOGGER.debug("Access log read did not finish before unload")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
