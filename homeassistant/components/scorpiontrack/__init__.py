"""The ScorpionTrack integration."""

from __future__ import annotations

from typing import NoReturn

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShareUnavailableError,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import CONF_SHARE_TOKEN, PLATFORMS
from .coordinator import ScorpionTrackConfigEntry, ScorpionTrackCoordinator


def _raise_first_refresh_error(err: ConfigEntryNotReady) -> NoReturn:
    """Re-map first-refresh failures into setup-time config entry errors."""
    cause = err.__cause__
    root_cause = cause.__cause__ if isinstance(cause, UpdateFailed) else cause

    if isinstance(root_cause, ScorpionTrackConnectionError):
        raise ConfigEntryNotReady(
            f"Could not reach ScorpionTrack share service: {root_cause}"
        ) from root_cause
    if isinstance(root_cause, ScorpionTrackInvalidTokenError):
        raise ConfigEntryError(
            f"The configured ScorpionTrack share token is invalid: {root_cause}"
        ) from root_cause
    if isinstance(root_cause, ScorpionTrackShareUnavailableError):
        raise ConfigEntryError(
            "The configured ScorpionTrack share is expired, revoked, or unavailable: "
            f"{root_cause}"
        ) from root_cause
    if cause is not None:
        raise ConfigEntryNotReady(str(cause)) from cause
    raise err


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
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        _raise_first_refresh_error(err)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ScorpionTrackConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
