"""Provides the OneTracker DataUpdateCoordinator."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import json
import logging
from typing import Any

from async_timeout import timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OneTrackerAPI, OneTrackerAPIException
from .api_responses import Parcel
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OneTrackerDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching OneTracker data."""

    api: OneTrackerAPI

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config: Mapping[str, Any],
        _options: Mapping[str, Any] | None = None,
    ) -> None:
        """Initialize global OneTracker data updater."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

        self.api = OneTrackerAPI(config)

    async def _async_update_data(self) -> list[Parcel]:
        """Fetch data from OneTracker."""

        def _update_data() -> list[Parcel]:
            """Fetch data from OneTracker via sync functions."""

            parcels = self.api.get_parcels()

            # for parcel in parcels:
            #     self.hass.states.set(
            #         f"{DOMAIN}.{parcel.id}",
            #         "parcel",
            #         parcel.serialize(),
            #     )
            # self.data = {"parcels": map(lambda p: p.serialize(), parcels)}
            return parcels

        try:
            async with timeout(4):
                return await self.hass.async_add_executor_job(_update_data)
        except OneTrackerAPIException as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
