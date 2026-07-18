"""Coordinator for ScorpionTrack."""

import logging
from typing import override

from pyscorpiontrack import (
    ScorpionTrackClient,
    ScorpionTrackConnectionError,
    ScorpionTrackInvalidTokenError,
    ScorpionTrackShare,
    ScorpionTrackShareUnavailableError,
    ScorpionTrackVehicle,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ACTIVE_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

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
        self._previous_share_had_active_vehicle = False
        self.vehicles_by_id: dict[int, ScorpionTrackVehicle] = {}
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            always_update=False,
        )

    @override
    async def _async_update_data(self) -> ScorpionTrackShare:
        """Fetch updated share data."""
        try:
            share = await self.client.async_get_share()
        except ScorpionTrackConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                retry_after=DEFAULT_SCAN_INTERVAL.total_seconds(),
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
        else:
            self.vehicles_by_id = {vehicle.id: vehicle for vehicle in share.vehicles}
            share_has_active_vehicle = any(
                vehicle.position.ignition is True for vehicle in share.vehicles
            )
            self.update_interval = (
                ACTIVE_SCAN_INTERVAL
                if share_has_active_vehicle or self._previous_share_had_active_vehicle
                else DEFAULT_SCAN_INTERVAL
            )
            self._previous_share_had_active_vehicle = share_has_active_vehicle
            return share
