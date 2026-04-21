"""DataUpdateCoordinator for the Russound RNET integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
import logging

from aiorussound.rnet.client import RNETZoneInfo, RussoundRNETClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MODEL, CONF_ZONES, DOMAIN, RNET_EXCEPTIONS, RNET_MODELS

_LOGGER = logging.getLogger(__name__)

# Small delay between zone polls to avoid overwhelming serial bridges
_INTER_ZONE_DELAY = 0.1

type RussoundRNETConfigEntry = ConfigEntry[RussoundRNETCoordinator]


class RussoundRNETCoordinator(
    DataUpdateCoordinator[dict[tuple[int, int], RNETZoneInfo]]
):
    """Coordinator for polling Russound RNET zones."""

    config_entry: RussoundRNETConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: RussoundRNETConfigEntry,
        client: RussoundRNETClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self._lock = asyncio.Lock()
        model_key = entry.data[CONF_MODEL]
        self._model = RNET_MODELS[model_key]

        # Build list of (controller_id, zone_id) tuples to poll
        zones_config = entry.data.get(CONF_ZONES, {})
        if zones_config:
            self._zone_keys: list[tuple[int, int]] = [
                (int(key.split("_")[0]), int(key.split("_")[1])) for key in zones_config
            ]
        else:
            # No zones configured — poll all model zones
            self._zone_keys = [
                (c, z)
                for c in range(1, self._model.max_controllers + 1)
                for z in range(1, self._model.max_zones + 1)
            ]

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_setup(self) -> None:
        """Set up the coordinator — connect to the device."""
        try:
            await self.client.connect()
        except RNET_EXCEPTIONS as err:
            raise UpdateFailed(f"Cannot connect to RNET device: {err}") from err

    async def _async_update_data(self) -> dict[tuple[int, int], RNETZoneInfo]:
        """Poll all zones and return zone data keyed by (controller_id, zone_id)."""
        async with self._lock:
            return await self._poll_zones()

    async def _poll_zones(self) -> dict[tuple[int, int], RNETZoneInfo]:
        """Poll all zones (must be called under lock)."""
        data: dict[tuple[int, int], RNETZoneInfo] = {}

        if not self.client.is_connected:
            try:
                await self.client.connect()
            except RNET_EXCEPTIONS as err:
                raise UpdateFailed(f"Cannot reconnect to RNET device: {err}") from err

        try:
            for controller_id, zone_id in self._zone_keys:
                info = await self.client.get_all_zone_info(controller_id, zone_id)
                data[(controller_id, zone_id)] = info
                await asyncio.sleep(_INTER_ZONE_DELAY)
        except RNET_EXCEPTIONS as err:
            # Disconnect on error so next poll reconnects cleanly
            with suppress(*RNET_EXCEPTIONS):
                await self.client.disconnect()
            raise UpdateFailed(f"Error polling RNET zones: {err}") from err

        return data

    async def async_refresh_zone(
        self,
        controller_id: int,
        zone_id: int,
    ) -> None:
        """Poll only the affected zone for instant feedback after a command."""
        try:
            info = await self.client.get_all_zone_info(controller_id, zone_id)
        except RNET_EXCEPTIONS:
            return
        if self.data is not None:
            self.data[(controller_id, zone_id)] = info
            self.async_set_updated_data(self.data)

    async def async_shutdown(self) -> None:
        """Disconnect the client on shutdown."""
        await super().async_shutdown()
        with suppress(*RNET_EXCEPTIONS):
            await self.client.disconnect()
