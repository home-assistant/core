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
from homeassistant.core import HomeAssistant, callback
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

# The destructive access-log read in flight for an entry, if any. Kept out of
# the entry's runtime data on purpose: unloading only waits a bounded time, so
# a slow read outlives the entry it started under. Runtime data is replaced on
# reload, and a fresh copy would hide the running read from the new lock
# entity, which would then open a second BLE session over a log the first one
# is still draining. Unloading waits on whatever is registered here.
ACCESS_LOG_READS: HassKey[dict[str, asyncio.Task[None]]] = HassKey(
    f"{DOMAIN}_access_log_reads"
)

# The mutex serialising every BLE session with one lock, by entry id. Kept
# here for the same reason as ACCESS_LOG_READS: the lock accepts a single
# connection at a time, and a read that outlives its entity has to keep
# excluding the replacement entity's polls and unlocks. A mutex on the entity
# cannot do that — the replacement starts with a fresh one and would open a
# second session over the log the old read is still draining.
BLE_LOCKS: HassKey[dict[str, asyncio.Lock]] = HassKey(f"{DOMAIN}_ble_locks")


@callback
def async_get_ble_lock(hass: HomeAssistant, entry_id: str) -> asyncio.Lock:
    """Return the BLE mutex shared by everything talking to one lock."""
    return hass.data.setdefault(BLE_LOCKS, {}).setdefault(entry_id, asyncio.Lock())


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
    read = hass.data.get(ACCESS_LOG_READS, {}).get(entry.entry_id)
    if read is not None and not read.done():
        try:
            async with asyncio.timeout(ACCESS_LOG_UNLOAD_TIMEOUT):
                await asyncio.shield(read)
        except TimeoutError, HomeAssistantError:
            _LOGGER.debug("Access log read did not finish before unload")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> None:
    """Drop the state deliberately kept outside the entry, once it is gone.

    All of it outlives an unload on purpose, so a reload finds it again; only
    deleting the entry means nothing will come back for it.
    """
    entry_id = entry.entry_id
    hass.data.get(BLE_LOCKS, {}).pop(entry_id, None)
    read = hass.data.get(ACCESS_LOG_READS, {}).pop(entry_id, None)

    def _drop_pending() -> None:
        hass.data.get(PENDING_LOG_ENTRIES, {}).pop(entry_id, None)

    if read is not None and not read.done():
        # A read that outran the unload wait is still draining the lock, and
        # buffers everything it reports once runtime_data is gone. Clearing
        # now would let it refill the buffer straight afterwards and leave
        # those entries in hass.data for good — nothing can consume them, the
        # entry is deleted — so wait for it to stop writing first.
        read.add_done_callback(lambda _: _drop_pending())
        return

    _drop_pending()
