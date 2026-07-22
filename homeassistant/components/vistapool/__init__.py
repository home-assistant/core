"""The Vistapool integration."""

import asyncio
from dataclasses import dataclass, field
import logging

from aioaquarite import (
    AquariteAuth,
    AquariteClient,
    AquariteError,
    AuthenticationError,
    ResilientUserPoolsSubscription,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_NEW_POOL
from .coordinator import VistapoolDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


@dataclass
class VistapoolData:
    """Runtime data for a Vistapool account (holds one coordinator per pool)."""

    auth: AquariteAuth
    api: AquariteClient
    coordinators: dict[str, VistapoolDataUpdateCoordinator] = field(
        default_factory=dict
    )
    sync_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


type VistapoolConfigEntry = ConfigEntry[VistapoolData]


async def async_setup_entry(hass: HomeAssistant, entry: VistapoolConfigEntry) -> bool:
    """Set up Vistapool from a config entry.

    One config entry represents a Hayward account; the account can contain
    multiple pools, each exposed as a separate device.
    """
    user_config = entry.data
    session = async_get_clientsession(hass)

    auth = AquariteAuth(session, user_config[CONF_USERNAME], user_config[CONF_PASSWORD])
    try:
        await auth.authenticate()
    except AuthenticationError as exc:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_credentials",
        ) from exc
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    api = AquariteClient(auth)
    try:
        pools = await api.get_pools()
    except AquariteError as exc:
        raise ConfigEntryNotReady from exc

    if not pools:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="no_pools",
        )

    data = VistapoolData(auth=auth, api=api)
    entry.runtime_data = data

    try:
        for pool_id, pool_name in pools.items():
            await _async_add_coordinator(hass, entry, pool_id, pool_name, first=True)
    except Exception:
        for coordinator in data.coordinators.values():
            await coordinator.async_shutdown()
        raise

    # Catch pools removed from the account while Home Assistant was offline; the
    # first live snapshot is a no-op so it wouldn't clean these up.
    _async_remove_stale_devices(hass, entry, set(pools))

    def _on_user_pools_snapshot(pool_ids: list[str]) -> None:
        """Bridge the Firestore snapshot from the watch thread to the HA loop."""
        hass.loop.call_soon_threadsafe(_schedule_reconcile, pool_ids)

    @callback
    def _schedule_reconcile(pool_ids: list[str]) -> None:
        entry.async_create_background_task(
            hass,
            _async_reconcile_pools(hass, entry, pool_ids),
            name=f"vistapool_reconcile_{entry.entry_id}",
        )

    # Subscribe before forwarding platforms so a failed subscribe doesn't leave
    # platforms set up; on retry they would re-forward and raise "already setup".
    try:
        subscription: ResilientUserPoolsSubscription = (
            await api.subscribe_user_pools_resilient(_on_user_pools_snapshot)
        )
    except AquariteError as exc:
        for coordinator in data.coordinators.values():
            await coordinator.async_shutdown()
        raise ConfigEntryNotReady from exc
    entry.async_on_unload(subscription.aclose)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VistapoolConfigEntry) -> bool:
    """Unload Vistapool config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Hold sync_lock so a reconcile background task can't mutate the
        # coordinators dict while we shut it down.
        async with entry.runtime_data.sync_lock:
            for coordinator in entry.runtime_data.coordinators.values():
                await coordinator.async_shutdown()
    return unload_ok


@callback
def _async_remove_stale_devices(
    hass: HomeAssistant, entry: VistapoolConfigEntry, valid_pool_ids: set[str]
) -> None:
    """Remove registry devices for pools no longer present on the account."""
    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        pool_id = next((i[1] for i in device.identifiers if i[0] == DOMAIN), None)
        if pool_id is not None and pool_id not in valid_pool_ids:
            device_registry.async_remove_device(device.id)


async def _async_initial_refresh(
    coordinator: VistapoolDataUpdateCoordinator, *, first: bool
) -> None:
    """Populate coordinator data for a pool; raise if it would stay empty."""
    if first:
        await coordinator.async_config_entry_first_refresh()
        return
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="update_failed",
        )


async def _async_add_coordinator(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    pool_id: str,
    pool_name: str,
    *,
    first: bool,
) -> VistapoolDataUpdateCoordinator:
    """Create, refresh and subscribe a coordinator for a single pool."""
    coordinator = VistapoolDataUpdateCoordinator(
        hass, entry, entry.runtime_data.auth, entry.runtime_data.api, pool_id, pool_name
    )
    try:
        await _async_initial_refresh(coordinator, first=first)
        try:
            await coordinator.subscribe()
        except AquariteError as exc:
            raise ConfigEntryNotReady from exc
    except ConfigEntryNotReady:
        await coordinator.async_shutdown()
        raise
    entry.runtime_data.coordinators[pool_id] = coordinator
    return coordinator


async def _async_reconcile_pools(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    pool_ids: list[str],
) -> None:
    """Reconcile the runtime coordinator set against a fresh pool ID list."""
    async with entry.runtime_data.sync_lock:
        current = set(entry.runtime_data.coordinators)
        fetched = set(pool_ids)
        if current == fetched:
            return

        new_ids = fetched - current
        names: dict[str, str] = {}
        if new_ids:
            try:
                names = await entry.runtime_data.api.get_pools()
            except AquariteError as err:
                _LOGGER.debug("Pool name lookup failed during reconcile: %s", err)
                new_ids = set()

        for pool_id in new_ids:
            if pool_id not in names:
                continue
            try:
                coordinator = await _async_add_coordinator(
                    hass, entry, pool_id, names[pool_id], first=False
                )
            except ConfigEntryNotReady as err:
                _LOGGER.warning("Failed to add new pool %s: %s", pool_id, err)
                continue
            async_dispatcher_send(
                hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", coordinator
            )

        if stale := current - fetched:
            for pool_id in stale:
                await entry.runtime_data.coordinators.pop(pool_id).async_shutdown()
            _async_remove_stale_devices(hass, entry, fetched)
