"""Coordinator for Watergate API."""

from datetime import timedelta
import logging

from watergate_local_api import WatergateApiException, WatergateLocalApiClient
from watergate_local_api.models import (
    AutoShutOffReport,
    DeviceState,
    NetworkingData,
    TelemetryData,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WatergateAgregatedRequests:
    """Class to hold aggregated requests."""

    def __init__(
        self,
        state: DeviceState,
        telemetry: TelemetryData,
        networking: NetworkingData,
        auto_shut_off_report: AutoShutOffReport,
    ) -> None:
        """Initialize aggregated requests."""
        self.state = state
        self.telemetry = telemetry
        self.networking = networking
        self.auto_shut_off_report = auto_shut_off_report


class WatergateDataCoordinator(DataUpdateCoordinator[WatergateAgregatedRequests]):
    """Class to manage fetching watergate data."""

    def __init__(self, hass: HomeAssistant, api: WatergateLocalApiClient) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=2),
        )
        self.api = api

    async def _async_update_data(self) -> WatergateAgregatedRequests:
        try:
            state = await self.api.async_get_device_state()
            telemetry = await self.api.async_get_telemetry_data()
            networking = await self.api.async_get_networking()
            auto_shut_off_report = await self.api.async_get_auto_shut_off_report()
            return WatergateAgregatedRequests(
                state,
                telemetry,
                networking,
                auto_shut_off_report,
            )
        except WatergateApiException as exc:
            raise UpdateFailed(f"Sonic device is unavailable: {exc}") from exc

    def async_set_updated_data(self, data: WatergateAgregatedRequests) -> None:
        """Manually update data, notify listeners and DO NOT reset refresh interval."""

        self.data = data
        self.logger.debug(
            "Manually updated %s data",
            self.name,
        )

        self.async_update_listeners()
