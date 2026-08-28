"""The Marstek integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import DOMAIN
from .coordinator import (
    MarstekConfigEntry,
    MarstekDataUpdateCoordinator,
    MarstekRuntimeData,
    MarstekSharedData,
)
from .helpers import async_create_udp_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _async_get_shared_data(
    hass: HomeAssistant, current_entry: MarstekConfigEntry
) -> MarstekSharedData | None:
    """Return shared runtime data from another Marstek config entry."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry is current_entry or not hasattr(entry, "runtime_data"):
            continue
        return entry.runtime_data.shared_data
    return None


async def _async_release_udp_client(data: MarstekSharedData) -> None:
    """Release a reference to the shared UDP client."""
    data.entry_count -= 1
    if data.entry_count == 0:
        await data.udp_client.async_cleanup()


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    shared_data = _async_get_shared_data(hass, entry)
    if shared_data is None:
        try:
            udp_client = await async_create_udp_client(hass)
        except (TimeoutError, OSError, TypeError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="udp_client_setup_failed",
            ) from err
        shared_data = MarstekSharedData(udp_client=udp_client)
    shared_data.entry_count += 1

    coordinator = MarstekDataUpdateCoordinator(hass, entry, shared_data.udp_client)
    entry.runtime_data = MarstekRuntimeData(
        coordinator=coordinator, shared_data=shared_data
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady:
        await _async_release_udp_client(shared_data)
        object.__delattr__(entry, "runtime_data")
        raise

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await _async_release_udp_client(entry.runtime_data.shared_data)

    return unload_ok
