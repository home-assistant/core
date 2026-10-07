"""The ENGIE Belgium integration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from aioengiebelgium import EngieBeClient, EngieBeError

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_REFRESH_TOKEN, CONTRACTS_RETRY_INTERVAL, LOGGER
from .coordinator import (
    EngieBeEpexCoordinator,
    EngieBePricesCoordinator,
    EngieBeRelationsCoordinator,
    mask_identifier,
)

_PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


@dataclass
class EngieBeHouseholdCoordinators:
    """Per-household coordinators and tariff state."""

    prices: EngieBePricesCoordinator
    is_dynamic: bool | None


@dataclass
class EngieBeRuntimeData:
    """Runtime data for the ENGIE Belgium integration."""

    client: EngieBeClient
    relations: EngieBeRelationsCoordinator
    epex: EngieBeEpexCoordinator | None
    households: dict[str, EngieBeHouseholdCoordinators]
    epex_ready_callbacks: list[Callable[[], None]] = field(default_factory=list)


type EngieBeConfigEntry = ConfigEntry[EngieBeRuntimeData]


async def _async_is_dynamic(client: EngieBeClient, ban: str) -> bool | None:
    """Return whether one business agreement has a dynamic electricity tariff."""
    try:
        contracts = await client.async_get_energy_contracts(ban)
    except EngieBeError as err:
        LOGGER.debug(
            "Fetching energy contracts for %s failed: %s",
            mask_identifier(ban),
            err,
        )
        return None
    return contracts.is_dynamic()


async def async_setup_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
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

    @callback
    def _async_create_household(
        ban: str, is_dynamic: bool | None
    ) -> EngieBeHouseholdCoordinators:
        """Build the coordinators for a business agreement and register its device."""
        household = EngieBeHouseholdCoordinators(
            prices=EngieBePricesCoordinator(
                hass, entry, client, ban, relations.data[ban]
            ),
            is_dynamic=is_dynamic,
        )
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **household.prices.device_info
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
        *(household.prices.async_refresh() for household in households.values())
    )
    if epex is not None:
        try:
            await epex.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            LOGGER.warning("EPEX prices unavailable at setup: %s", err.__cause__)

    entry.runtime_data = EngieBeRuntimeData(
        client=client,
        relations=relations,
        epex=epex,
        households=households,
    )

    if epex is not None and any(
        household.is_dynamic is None for household in households.values()
    ):
        LOGGER.warning("Tariff lookup failed, EPEX entities wait for a retry")
        _async_start_tariff_retry(hass, entry, epex)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


@callback
def _async_start_tariff_retry(
    hass: HomeAssistant, entry: EngieBeConfigEntry, epex: EngieBeEpexCoordinator
) -> None:
    """Retry the tariff lookup of the households whose lookup failed at setup."""
    runtime_data = entry.runtime_data
    households = runtime_data.households

    async def _async_retry_classification() -> None:
        """Classify the pending households and stop once none is left."""
        pending = [
            ban for ban, household in households.items() if household.is_dynamic is None
        ]
        results = await asyncio.gather(
            *(_async_is_dynamic(runtime_data.client, ban) for ban in pending)
        )
        if entry.state is not ConfigEntryState.LOADED:
            return
        for ban, is_dynamic in zip(pending, results, strict=True):
            households[ban].is_dynamic = is_dynamic
        if any(results):
            await epex.async_request_refresh()
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


async def async_unload_entry(hass: HomeAssistant, entry: EngieBeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
