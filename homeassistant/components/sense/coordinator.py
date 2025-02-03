"""Sense Coordinators."""

from datetime import timedelta
import logging

from sense_energy import (
    ASyncSenseable,
    SenseAuthenticationException,
    SenseMFARequiredException,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACTIVE_UPDATE_RATE,
    SENSE_CONNECT_EXCEPTIONS,
    SENSE_TIMEOUT_EXCEPTIONS,
    SENSE_WEBSOCKET_EXCEPTIONS,
    TREND_UPDATE_RATE,
)

_LOGGER = logging.getLogger(__name__)


class SenseCoordinator(DataUpdateCoordinator[None]):
    """Sense Trend Coordinator."""

    def __init__(
        self, hass: HomeAssistant, gateway: ASyncSenseable, name: str, update: int
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Sense {name} {gateway.sense_monitor_id}",
            update_interval=timedelta(seconds=update),
        )
        self._gateway = gateway
        self.last_update_success = False


class SenseTrendCoordinator(SenseCoordinator):
    """Sense Trend Coordinator."""

    def __init__(self, hass: HomeAssistant, gateway: ASyncSenseable) -> None:
        """Initialize."""
        super().__init__(hass, gateway, "Trends", TREND_UPDATE_RATE)

    async def _async_update_data(self) -> None:
        """Update the trend data."""
        try:
            await self._gateway.update_trend_data()
        except (SenseAuthenticationException, SenseMFARequiredException) as err:
            _LOGGER.warning("Sense authentication expired")
            raise ConfigEntryAuthFailed(err) from err
        except SENSE_CONNECT_EXCEPTIONS as err:
            raise UpdateFailed(err) from err


class SenseRealtimeCoordinator(SenseCoordinator):
    """Sense Realtime Coordinator."""

    def __init__(self, hass: HomeAssistant, gateway: ASyncSenseable) -> None:
        """Initialize."""
        super().__init__(hass, gateway, "Realtime", ACTIVE_UPDATE_RATE)

    async def _async_update_data(self) -> None:
        """Retrieve latest state."""
        try:
            await self._gateway.update_realtime()
        except SENSE_TIMEOUT_EXCEPTIONS as ex:
            _LOGGER.error("Timeout retrieving data: %s", ex)
        except SENSE_WEBSOCKET_EXCEPTIONS as ex:
            _LOGGER.error("Failed to update data: %s", ex)
