"""Coordinator for Watergate API."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from watergate_local_api import WatergateApiException, WatergateLocalApiClient
from watergate_local_api.models import DeviceState, NetworkingData, TelemetryData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class WatergateAgregatedRequests:
    """Class to hold aggregated requests."""

    state: DeviceState
    telemetry: TelemetryData
    networking: NetworkingData


type WatergateConfigEntry = ConfigEntry[WatergateDataCoordinator]


class WatergateDataCoordinator(DataUpdateCoordinator[WatergateAgregatedRequests]):
    """Class to manage fetching watergate data."""

    config_entry: WatergateConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WatergateConfigEntry,
        api: WatergateLocalApiClient,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=2),
        )
        self.api = api

    async def _async_update_data(self) -> WatergateAgregatedRequests:
        try:
            state = await self.api.async_get_device_state()
            telemetry = await self.api.async_get_telemetry_data()
            networking = await self.api.async_get_networking()
        except WatergateApiException as exc:
            raise UpdateFailed(f"Sonic device is unavailable: {exc}") from exc
        return WatergateAgregatedRequests(state, telemetry, networking)

    def async_set_updated_data(self, data: WatergateAgregatedRequests) -> None:
        """Manually update data, notify listeners and DO NOT reset refresh interval."""

        self.data = data
        self.logger.debug(
            "Manually updated %s data",
            self.name,
        )

        self.async_update_listeners()
