"""Contains the shared Coordinator for Starlink systems."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from starlink_grpc import ChannelContext, GrpcError, get_status

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .dish_status import DishyStatus

_LOGGER = logging.getLogger(__name__)


class StarlinkUpdateCoordinator(DataUpdateCoordinator[DishyStatus]):
    """Coordinates updates between all Starlink sensors defined in this file."""

    def __init__(self, hass: HomeAssistant, name: str, url: str) -> None:
        """Initialize an UpdateCoordinator for a group of sensors."""
        self.channel_context = ChannelContext(target=url)

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=1),
        )

    async def _async_update_data(self) -> DishyStatus:
        async with async_timeout.timeout(1):
            try:
                status = await self.hass.async_add_executor_job(
                    lambda: get_status(self.channel_context)
                )
                device_info = status.device_info
                device_state = status.device_state
                obstruction_stats = status.obstruction_stats
                return DishyStatus(
                    id=device_info.id,
                    hardware_version=device_info.hardware_version,
                    software_version=device_info.software_version,
                    boot_count=device_info.bootcount,
                    uptime=device_state.uptime_s,
                    downlink_throughput_bps=status.downlink_throughput_bps,
                    uplink_throughput_bps=status.uplink_throughput_bps,
                    pop_ping_latency_ms=status.pop_ping_latency_ms,
                    snr_good=status.is_snr_above_noise_floor,
                    avg_obstruction_duration=obstruction_stats.avg_prolonged_obstruction_interval_s,
                    connection_valid_time=obstruction_stats.valid_s,
                    direction_azimuth=status.boresight_azimuth_deg,
                    direction_elevation=status.boresight_elevation_deg,
                )
            except GrpcError as exc:
                raise UpdateFailed from exc
