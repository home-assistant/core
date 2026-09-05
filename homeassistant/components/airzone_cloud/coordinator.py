"""The Airzone Cloud integration coordinator."""

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any, override

from aioairzone_cloud.cloudapi import AirzoneCloudApi
from aioairzone_cloud.const import AZD_AIDOOS, RAW_DEVICES_CONFIG
from aioairzone_cloud.exceptions import AirzoneCloudError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    AIOAIRZONE_CLOUD_TIMEOUT_SEC,
    API_SLATS_H_VALUES,
    API_SLATS_V_CONF,
    API_SLATS_V_VALUES,
    AZD_SLATS_H_VALUES,
    AZD_SLATS_V_CONF,
    AZD_SLATS_V_VALUES,
    DOMAIN,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

type AirzoneCloudConfigEntry = ConfigEntry[AirzoneUpdateCoordinator]


class AirzoneUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Airzone Cloud device."""

    config_entry: AirzoneCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AirzoneCloudConfigEntry,
        airzone: AirzoneCloudApi,
    ) -> None:
        """Initialize."""
        self.airzone = airzone
        self.airzone.set_update_callback(self._async_set_updated_data)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        async with timeout(AIOAIRZONE_CLOUD_TIMEOUT_SEC):
            try:
                await self.airzone.update()
            except AirzoneCloudError as error:
                raise UpdateFailed(error) from error
            return self.data_with_slats()

    @callback
    def _async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Enrich Airzone callback data before publishing it."""
        self.async_set_updated_data(self.data_with_slats(data))

    def data_with_slats(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return Airzone data with Aidoo slat fields from raw API config."""
        if data is None:
            data = self.airzone.data()
        aidoos = data.get(AZD_AIDOOS, {})
        raw_config = self.airzone.raw_data().get(RAW_DEVICES_CONFIG, {})

        for aidoo_id, aidoo_data in aidoos.items():
            if not (config := raw_config.get(aidoo_id)):
                continue
            if API_SLATS_V_CONF in config:
                aidoo_data[AZD_SLATS_V_CONF] = config[API_SLATS_V_CONF]
            if API_SLATS_V_VALUES in config:
                aidoo_data[AZD_SLATS_V_VALUES] = config[API_SLATS_V_VALUES]
            if API_SLATS_H_VALUES in config:
                aidoo_data[AZD_SLATS_H_VALUES] = config[API_SLATS_H_VALUES]

        return data
