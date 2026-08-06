"""The MobilityData integration."""

from pathlib import Path

from aiomobilitydatabase.feeds import MobilityFeedsClient

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import STORAGE_DIR

from .const import CONF_FEED_ID, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import (
    ArrivalsCoordinator,
    MobilityDataConfigEntry,
    MobilityDataRuntimeData,
    StaticCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _cache_dir(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(STORAGE_DIR, DOMAIN))


async def async_setup_entry(
    hass: HomeAssistant, entry: MobilityDataConfigEntry
) -> bool:
    """Set up MobilityData from a config entry."""
    client = MobilityFeedsClient(
        entry.data[CONF_REFRESH_TOKEN],
        session=async_get_clientsession(hass),
        cache_dir=_cache_dir(hass),
    )
    static_coordinator = StaticCoordinator(hass, entry, client)
    arrivals_coordinator = ArrivalsCoordinator(hass, entry, static_coordinator)
    entry.runtime_data = MobilityDataRuntimeData(
        client=client,
        static_coordinator=static_coordinator,
        arrivals_coordinator=arrivals_coordinator,
    )
    # No entity listens to the static coordinator, and an unlistened
    # coordinator never schedules its periodic refresh.
    entry.async_on_unload(static_coordinator.async_add_listener(lambda: None))
    # Subentry changes only fire update listeners; reload to (un)load sensors.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    # The first static refresh may be a full download + index build on a cold
    # cache; entities stay unavailable until it lands rather than blocking
    # setup or raising ConfigEntryNotReady.
    entry.async_create_background_task(
        hass,
        _async_initial_refresh(static_coordinator, arrivals_coordinator),
        name=f"{DOMAIN} initial refresh {entry.entry_id}",
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: MobilityDataConfigEntry
) -> None:
    """Reload the entry when its data or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_initial_refresh(
    static_coordinator: StaticCoordinator, arrivals_coordinator: ArrivalsCoordinator
) -> None:
    await static_coordinator.async_refresh()
    if static_coordinator.data is not None:
        await arrivals_coordinator.async_refresh()


async def async_unload_entry(
    hass: HomeAssistant, entry: MobilityDataConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if (handle := entry.runtime_data.static_coordinator.data) is not None:
            handle.close()
        await entry.runtime_data.client.close()
    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant, entry: MobilityDataConfigEntry
) -> None:
    """Purge the cached GTFS index when the entry is removed."""
    client = MobilityFeedsClient(
        entry.data[CONF_REFRESH_TOKEN], cache_dir=_cache_dir(hass)
    )
    try:
        await client.purge_cache(entry.data[CONF_FEED_ID])
    finally:
        await client.close()
