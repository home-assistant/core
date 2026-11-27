"""The ENGIE Belgium integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from aioengiebelgium import EngieBeAuthenticationError, EngieBeClient, EngieBeError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_REFRESH_TOKEN, CONTRACTS_RETRY_INTERVAL, DOMAIN, LOGGER
from .coordinator import (
    EngieBeEpexCoordinator,
    EngieBePeaksCoordinator,
    EngieBePricesCoordinator,
    EngieBeRelationsCoordinator,
    invalid_auth_error,
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

    relations: EngieBeRelationsCoordinator
    epex: EngieBeEpexCoordinator | None
    households: dict[str, EngieBeHouseholdCoordinators]
    epex_ready_callbacks: list[Callable[[], None]] = field(default_factory=list)

    @callback
    def async_add_epex_entities(
        self, add_entities: Callable[[EngieBeEpexCoordinator, list[str]], None]
    ) -> None:
        """Add EPEX entities for the dynamic households now and whenever more are found."""
        known_bans: set[str] = set()

        @callback
        def _async_add_new_households() -> None:
            """Pass the newly found dynamic households to add_entities."""
            if self.epex is None:
                return
            new_bans = [
                ban
                for ban, household in self.households.items()
                if household.is_dynamic and ban not in known_bans
            ]
            if not new_bans:
                return
            known_bans.update(new_bans)
            add_entities(self.epex, new_bans)

        self.epex_ready_callbacks.append(_async_add_new_households)
        _async_add_new_households()


type EngieBeConfigEntry = ConfigEntry[EngieBeRuntimeData]


async def _async_is_dynamic(client: EngieBeClient, ban: str) -> bool | None:
    """Return whether one business agreement has a dynamic electricity tariff."""
    try:
        contracts = await client.async_get_energy_contracts(ban)
    except EngieBeAuthenticationError as err:
        raise invalid_auth_error() from err
    except EngieBeError as err:
        LOGGER.debug(
            "Fetching energy contracts for %s failed: %s",
            mask_identifier(ban),
            err,
        )
        return None
    return contracts.is_dynamic()


@callback
def _async_remove_stale_devices(
    device_registry: dr.DeviceRegistry, entry: EngieBeConfigEntry, bans: set[str]
) -> None:
    """Remove the devices of business agreements the account no longer lists."""
    identifiers = {(DOMAIN, ban) for ban in bans}
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        if device_entry.identifiers.isdisjoint(identifiers):
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

    device_registry = dr.async_get(hass)
    if relations.data:
        _async_remove_stale_devices(device_registry, entry, set(relations.data))

    @callback
    def _async_create_household(
        ban: str, is_dynamic: bool | None
    ) -> EngieBeHouseholdCoordinators:
        """Build the coordinators for a business agreement and register its device."""
        household = EngieBeHouseholdCoordinators(
            prices=EngieBePricesCoordinator(
                hass, entry, client, ban, relations.data[ban]
            ),
            peaks=EngieBePeaksCoordinator(hass, entry, client, ban),
            is_dynamic=is_dynamic,
        )
        device_registry.async_get_or_create_from_info(
            config_entry_id=entry.entry_id, device_info=household.prices.device_info
        )
        return household

    dynamic_flags = await asyncio.gather(
        *(_async_is_dynamic(client, ban) for ban in relations.data)
    )
    households = {
        ban: _async_create_household(ban, is_dynamic)
        for ban, is_dynamic in zip(relations.data, dynamic_flags, strict=True)
    }

    epex: EngieBeEpexCoordinator | None = None
    if any(household.is_dynamic is not False for household in households.values()):
        epex = EngieBeEpexCoordinator(hass, entry, client)

    await asyncio.gather(
        *(
            refresh
            for household in households.values()
            for refresh in (
                household.prices.async_refresh(),
                household.peaks.async_refresh(),
            )
        )
    )
    if epex is not None:
        try:
            await epex.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            LOGGER.warning("EPEX prices unavailable at setup: %s", err.__cause__)

    entry.runtime_data = EngieBeRuntimeData(
        relations=relations,
        epex=epex,
        households=households,
    )

    if epex is not None and any(
        household.is_dynamic is None for household in households.values()
    ):
        LOGGER.warning("Tariff lookup failed, EPEX entities wait for a retry")
        _async_start_tariff_retry(hass, entry, client, epex)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


@callback
def _async_start_tariff_retry(
    hass: HomeAssistant,
    entry: EngieBeConfigEntry,
    client: EngieBeClient,
    epex: EngieBeEpexCoordinator,
) -> None:
    """Retry the tariff lookup of the households whose lookup failed at setup."""
    runtime_data = entry.runtime_data
    households = runtime_data.households

    async def _async_retry_classification() -> None:
        """Classify the pending households and stop once none is left."""
        pending = [
            ban for ban, household in households.items() if household.is_dynamic is None
        ]
        try:
            results = await asyncio.gather(
                *(_async_is_dynamic(client, ban) for ban in pending)
            )
        except ConfigEntryAuthFailed:
            cancel_retry()
            entry.async_start_reauth(hass)
            return
        if entry.state is not ConfigEntryState.LOADED:
            return
        for ban, is_dynamic in zip(pending, results, strict=True):
            households[ban].is_dynamic = is_dynamic
        if any(results):
            await epex.async_request_refresh()
            if entry.state is not ConfigEntryState.LOADED:
                return  # type: ignore[unreachable]
            for notify in runtime_data.epex_ready_callbacks:
                notify()
        if any(household.is_dynamic is None for household in households.values()):
            return
        cancel_retry()
        if not any(household.is_dynamic for household in households.values()):
            await epex.async_shutdown()
            runtime_data.epex = None

    @callback
    def _start_retry_classification(_now: datetime) -> None:
        """Run a tariff retry as a task that stops when the entry unloads."""
        entry.async_create_background_task(
            hass, _async_retry_classification(), "engie_be tariff retry"
        )

    cancel_retry = async_track_time_interval(
        hass, _start_retry_classification, CONTRACTS_RETRY_INTERVAL
    )
    entry.async_on_unload(cancel_retry)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: EngieBeConfigEntry, device_entry: dr.AnyDeviceEntry
) -> bool:
    """Allow removing the device of a business agreement the account no longer lists."""
    if entry.state is not ConfigEntryState.LOADED:
        return False
    return not any(
        domain == DOMAIN and ban in entry.runtime_data.relations.data
        for domain, ban in device_entry.identifiers
    )


async def async_unload_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)
