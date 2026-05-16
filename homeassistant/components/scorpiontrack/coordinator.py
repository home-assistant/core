"""Coordinator for ScorpionTrack."""

import logging

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


type ScorpionTrackConfigEntry = ConfigEntry[ScorpionTrackCoordinator]


class ScorpionTrackCoordinator(DataUpdateCoordinator[ScorpionTrackShare]):
    """Coordinate shared-location updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ScorpionTrackClient,
        entry: ScorpionTrackConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )

    async def _async_update_data(self) -> ScorpionTrackShare:
        """Fetch updated share data."""
        try:
            return await self.client.async_get_share()
        except ScorpionTrackConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except ScorpionTrackInvalidTokenError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_token",
            ) from err
        except ScorpionTrackShareUnavailableError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="share_unavailable",
            ) from err
