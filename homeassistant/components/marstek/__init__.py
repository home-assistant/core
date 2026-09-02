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
    MARSTEK_SHARED_DATA,
    MarstekConfigEntry,
    MarstekDataUpdateCoordinator,
    MarstekRuntimeData,
    MarstekSharedData,
)
from .helpers import async_create_udp_client

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def _async_release_udp_client(
    hass: HomeAssistant, data: MarstekSharedData
) -> None:
    """Release a reference to the shared UDP client."""
    data.entry_count -= 1
    if data.entry_count == 0:
        await data.udp_client.async_cleanup()
        hass.data.pop(MARSTEK_SHARED_DATA, None)


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    shared_data = hass.data.get(MARSTEK_SHARED_DATA)
    if shared_data is None:
        try:
            udp_client = await async_create_udp_client(hass)
        except (TimeoutError, OSError, TypeError) as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="udp_client_setup_failed",
            ) from err
        shared_data = MarstekSharedData(udp_client=udp_client)
        hass.data[MARSTEK_SHARED_DATA] = shared_data
    shared_data.entry_count += 1

    coordinator = MarstekDataUpdateCoordinator(hass, entry, shared_data.udp_client)
    entry.runtime_data = MarstekRuntimeData(coordinator=coordinator)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed, ConfigEntryError, ConfigEntryNotReady:
        await _async_release_udp_client(hass, shared_data)
        object.__delattr__(entry, "runtime_data")
        raise

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await _async_release_udp_client(hass, hass.data[MARSTEK_SHARED_DATA])

    return unload_ok
