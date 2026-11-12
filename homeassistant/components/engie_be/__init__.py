"""The ENGIE Belgium integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial

from aioengiebelgium import EngieBeAuthenticationError, EngieBeClient, EngieBeError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_REFRESH_TOKEN,
    CONTRACTS_RETRY_INTERVAL,
    DOMAIN,
    LOGGER,
    NEW_HOUSEHOLDS_SIGNAL,
    REMOVED_HOUSEHOLDS_SIGNAL,
)
from .coordinator import (
    EngieBeEpexCoordinator,
    EngieBePeaksCoordinator,
    EngieBePricesCoordinator,
    EngieBeRelationsCoordinator,
    mask_identifier,
)

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class EngieBeHouseholdCoordinators:
    """Per-household coordinators and tariff state."""

    prices: EngieBePricesCoordinator
    peaks: EngieBePeaksCoordinator
    is_dynamic: bool | None


@dataclass
class EngieBeRuntimeData:
    """Runtime data for the ENGIE Belgium integration."""

    client: EngieBeClient
    relations: EngieBeRelationsCoordinator
    epex: EngieBeEpexCoordinator | None
    households: dict[str, EngieBeHouseholdCoordinators]
    epex_ready_callbacks: list[Callable[[], None]] = field(default_factory=list)
    household_sync_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    tariff_retry_unsub: Callable[[], None] | None = None


type EngieBeConfigEntry = ConfigEntry[EngieBeRuntimeData]


async def _async_is_dynamic(client: EngieBeClient, ban: str) -> bool | None:
    """Return whether one business agreement has a dynamic electricity tariff."""
    try:
        contracts = await client.async_get_energy_contracts(ban)
    except EngieBeAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except EngieBeError as err:
        LOGGER.debug(
            "Fetching energy contracts for %s failed: %s",
            mask_identifier(ban),
            err,
        )
        return None
    return contracts.is_dynamic()


@callback
def _create_household(
    hass: HomeAssistant, entry: EngieBeConfigEntry, ban: str, is_dynamic: bool | None
) -> EngieBeHouseholdCoordinators:
    """Build the coordinators of a business agreement and register its device."""
    runtime_data = entry.runtime_data
    household = EngieBeHouseholdCoordinators(
        prices=EngieBePricesCoordinator(
            hass,
            entry,
            runtime_data.client,
            ban,
            runtime_data.relations.data[ban],
        ),
        peaks=EngieBePeaksCoordinator(hass, entry, runtime_data.client, ban),
        is_dynamic=is_dynamic,
    )
    dr.async_get(hass).async_get_or_create_from_info(
        config_entry_id=entry.entry_id, device_info=household.prices.device_info
    )
    return household


@callback
def _async_remove_stale_devices(
    hass: HomeAssistant, entry: EngieBeConfigEntry, bans: set[str]
) -> None:
    """Remove the devices of business agreements the account no longer lists."""
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if not any(
            domain == DOMAIN and ban in bans for domain, ban in device_entry.identifiers
        ):
            device_registry.async_remove_device(device_entry.id)


async def async_setup_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> None:
    """Set up ENGIE Belgium from a config entry."""

    async def _persist_tokens(access_token: str, refresh_token: str) -> None:
        """Persist rotated tokens to the config entry."""
        if (
            entry.data[CONF_ACCESS_TOKEN] == access_token
            and entry.data[CONF_REFRESH_TOKEN] == refresh_token
        ):
            return
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: access_token,
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )

    client = EngieBeClient(
        session=async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        on_token_refresh=_persist_tokens,
    )

    relations = EngieBeRelationsCoordinator(hass, entry, client)
    await relations.async_config_entry_first_refresh()

    if relations.data:
        _async_remove_stale_devices(hass, entry, set(relations.data))

    entry.runtime_data = EngieBeRuntimeData(
        client=client,
        relations=relations,
        epex=None,
        households={},
    )
    entry.async_on_unload(partial(_async_cancel_tariff_retry, entry.runtime_data))

    dynamic_flags = await asyncio.gather(
        *(_async_is_dynamic(client, ban) for ban in relations.data)
    )
    for ban, is_dynamic in zip(relations.data, dynamic_flags, strict=True):
        entry.runtime_data.households[ban] = _create_household(
            hass, entry, ban, is_dynamic
        )

    if any(
        household.is_dynamic is not False
        for household in entry.runtime_data.households.values()
    ):
        entry.runtime_data.epex = EngieBeEpexCoordinator(hass, entry, client)

    await asyncio.gather(
        *(
            refresh
            for household in entry.runtime_data.households.values()
            for refresh in (
                household.prices.async_refresh(),
                household.peaks.async_refresh(),
            )
        )
    )
    if entry.runtime_data.epex is not None:
        try:
            await entry.runtime_data.epex.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            LOGGER.warning("EPEX prices unavailable at setup: %s", err.__cause__)

    if entry.runtime_data.epex is not None and any(
        household.is_dynamic is None
        for household in entry.runtime_data.households.values()
    ):
        LOGGER.warning("Tariff lookup failed, EPEX entities wait for a retry")
        _async_start_tariff_retry(hass, entry)

    @callback
    def _async_schedule_household_sync() -> None:
        """Run the household sync as a task that stops when the entry unloads."""
        entry.async_create_background_task(
            hass, _async_sync_households(hass, entry), "engie_be household sync"
        )

    entry.async_on_unload(relations.async_add_listener(_async_schedule_household_sync))

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def _async_sync_households(
    hass: HomeAssistant, entry: EngieBeConfigEntry
) -> None:
    """Align the households with the account's current business agreements."""
    if entry.state is not ConfigEntryState.LOADED:
        return
    runtime_data = entry.runtime_data
    async with runtime_data.household_sync_lock:
        current_bans = set(runtime_data.relations.data)
        known_bans = set(runtime_data.households)
        if current_bans and (removed_bans := known_bans - current_bans):
            await _async_remove_households(hass, entry, removed_bans)
        if added_bans := current_bans - known_bans:
            await _async_add_households(hass, entry, added_bans)


async def _async_remove_households(
    hass: HomeAssistant, entry: EngieBeConfigEntry, bans: set[str]
) -> None:
    """Shut down the coordinators and remove the device of each household that left."""
    runtime_data = entry.runtime_data
    device_registry = dr.async_get(hass)
    for ban in bans:
        household = runtime_data.households.pop(ban)
        await asyncio.gather(
            household.prices.async_shutdown(), household.peaks.async_shutdown()
        )
        device_entry = device_registry.async_get_device_by_identifier(
            (DOMAIN, ban), entry.entry_id
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
    if runtime_data.epex is not None and not any(
        household.is_dynamic is not False
        for household in runtime_data.households.values()
    ):
        await runtime_data.epex.async_shutdown()
        runtime_data.epex = None
    async_dispatcher_send(hass, REMOVED_HOUSEHOLDS_SIGNAL.format(entry.entry_id), bans)


async def _async_add_households(
    hass: HomeAssistant, entry: EngieBeConfigEntry, bans: set[str]
) -> None:
    """Create the coordinators, device and entities of each household that joined."""
    runtime_data = entry.runtime_data
    try:
        dynamic_flags = await asyncio.gather(
            *(_async_is_dynamic(runtime_data.client, ban) for ban in bans)
        )
    except ConfigEntryAuthFailed:
        entry.async_start_reauth(hass)
        return
    for ban, is_dynamic in zip(bans, dynamic_flags, strict=True):
        runtime_data.households[ban] = _create_household(hass, entry, ban, is_dynamic)
    if runtime_data.epex is None and any(
        runtime_data.households[ban].is_dynamic is not False for ban in bans
    ):
        runtime_data.epex = EngieBeEpexCoordinator(hass, entry, runtime_data.client)
        await runtime_data.epex.async_refresh()
    households = [runtime_data.households[ban] for ban in bans]
    await asyncio.gather(
        *(
            refresh
            for household in households
            for refresh in (
                household.prices.async_refresh(),
                household.peaks.async_refresh(),
            )
        )
    )
    async_dispatcher_send(hass, NEW_HOUSEHOLDS_SIGNAL.format(entry.entry_id), bans)
    if any(runtime_data.households[ban].is_dynamic is None for ban in bans):
        _async_start_tariff_retry(hass, entry)


@callback
def _async_cancel_tariff_retry(runtime_data: EngieBeRuntimeData) -> None:
    """Stop the tariff retry timer of the entry."""
    if runtime_data.tariff_retry_unsub is not None:
        runtime_data.tariff_retry_unsub()
        runtime_data.tariff_retry_unsub = None


@callback
def _async_start_tariff_retry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> None:
    """Retry the tariff lookup of the households whose lookup failed."""
    runtime_data = entry.runtime_data
    if runtime_data.tariff_retry_unsub is not None:
        return
    households = runtime_data.households

    async def _async_retry_classification() -> None:
        """Classify the pending households and stop once none is left."""
        pending = [
            (ban, household)
            for ban, household in households.items()
            if household.is_dynamic is None
        ]
        try:
            results = await asyncio.gather(
                *(_async_is_dynamic(runtime_data.client, ban) for ban, _ in pending)
            )
        except ConfigEntryAuthFailed:
            _async_cancel_tariff_retry(runtime_data)
            entry.async_start_reauth(hass)
            return
        if entry.state is not ConfigEntryState.LOADED:
            return
        applied: list[bool | None] = []
        for (ban, household), is_dynamic in zip(pending, results, strict=True):
            if households.get(ban) is household:
                household.is_dynamic = is_dynamic
                applied.append(is_dynamic)
        if any(applied) and (epex := runtime_data.epex) is not None:
            await epex.async_request_refresh()
            if entry.state is not ConfigEntryState.LOADED:
                return  # type: ignore[unreachable]
            for notify in runtime_data.epex_ready_callbacks:
                notify()
        if any(household.is_dynamic is None for household in households.values()):
            return
        _async_cancel_tariff_retry(runtime_data)
        epex = runtime_data.epex
        if (
            not any(household.is_dynamic for household in households.values())
            and epex is not None
        ):
            await epex.async_shutdown()
            runtime_data.epex = None

    @callback
    def _start_retry_classification(_now: datetime) -> None:
        """Run a tariff retry as a task that stops when the entry unloads."""
        entry.async_create_background_task(
            hass, _async_retry_classification(), "engie_be tariff retry"
        )

    runtime_data.tariff_retry_unsub = async_track_time_interval(
        hass, _start_retry_classification, CONTRACTS_RETRY_INTERVAL
    )


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: EngieBeConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Remove the household of a business agreement the account no longer lists."""
    if entry.state is not ConfigEntryState.LOADED:
        return True
    runtime_data = entry.runtime_data
    bans = {ban for domain, ban in device_entry.identifiers if domain == DOMAIN}
    async with runtime_data.household_sync_lock:
        if bans & set(runtime_data.relations.data):
            return False
        if tracked := bans & set(runtime_data.households):
            await _async_remove_households(hass, entry, tracked)
        return True


async def async_unload_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
