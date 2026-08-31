"""Polling coordinator for SmartyPlants, with webhook push support."""

import asyncio
import logging
from typing import override

from pysmartyplants import (
    Sensor,
    SensorUpdate,
    SmartyPlantsAuthError,
    SmartyPlantsClient,
    SmartyPlantsError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SmartyPlantsConfigEntry = ConfigEntry[SmartyPlantsCoordinator]


class SmartyPlantsCoordinator(DataUpdateCoordinator[dict[str, Sensor]]):
    """Fetches all sensors on one schedule and indexes them by sensor id."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SmartyPlantsConfigEntry,
        client: SmartyPlantsClient,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        # Polls and pushes both write the cached sensors, so they take turns.
        # Without this a push that arrived while a poll was in flight would be
        # overwritten by the older readings that poll was about to store.
        self._lock = asyncio.Lock()

    @override
    async def _async_update_data(self) -> dict[str, Sensor]:
        """Poll the backend and key the sensors by id."""
        async with self._lock:
            try:
                sensors = await self.client.async_get_sensors()
            except SmartyPlantsAuthError as err:
                # Reported as an update failure rather than starting a re-auth
                # flow, which this integration does not offer yet.
                raise UpdateFailed(
                    translation_domain=DOMAIN, translation_key="invalid_auth"
                ) from err
            except SmartyPlantsError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                    translation_placeholders={"error": str(err)},
                ) from err

            return {sensor.id: sensor for sensor in sensors}

    async def async_apply_update(self, update: SensorUpdate) -> None:
        """Merge a pushed update into the cached sensors."""
        async with self._lock:
            data = self.data or {}
            if (existing := data.get(update.sensor_id)) is None:
                # Entities are built from the sensors present when the entry
                # was set up, so there is nothing here to update. The sensor
                # appears once the entry is reloaded.
                _LOGGER.debug("Ignoring push for unknown sensor %s", update.sensor_id)
                return

            self.async_set_updated_data(
                {**data, update.sensor_id: existing.merge(update)}
            )
