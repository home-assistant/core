"""The ScorpionTrack integration."""

from __future__ import annotations

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShareUnavailableError,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SHARE_TOKEN, PLATFORMS
from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ScorpionTrackConfigEntry
) -> bool:
    """Set up ScorpionTrack from a config entry."""
    client = ScorpionTrackClient(
        session=async_get_clientsession(hass),
        token=entry.data[CONF_SHARE_TOKEN],
    )
    coordinator = ScorpionTrackCoordinator(hass, client, entry)

    try:
        coordinator.async_set_updated_data(await client.async_get_share())
    except ScorpionTrackConnectionError as err:
        raise ConfigEntryNotReady(
            "Could not reach ScorpionTrack share service"
        ) from err
    except ScorpionTrackInvalidTokenError as err:
        raise ConfigEntryError(
            "The configured ScorpionTrack share token is invalid"
        ) from err
    except ScorpionTrackShareUnavailableError as err:
        raise ConfigEntryError(
            "The configured ScorpionTrack share is expired, revoked, or unavailable"
        ) from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ScorpionTrackConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
