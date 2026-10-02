"""Sense Coordinators."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from sense_energy import (
    ASyncSenseable,
    SenseAPIException,
    SenseAuthenticationException,
    SenseMFARequiredException,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import SenseConfigEntry

from .const import (
    ACTIVE_UPDATE_RATE,
    SENSE_CONNECT_EXCEPTIONS,
    SENSE_TIMEOUT_EXCEPTIONS,
    SENSE_WEBSOCKET_EXCEPTIONS,
)
from .statistics import SenseStatistics

_LOGGER = logging.getLogger(__name__)


class SenseCoordinator(DataUpdateCoordinator[None]):
    """Sense Trend Coordinator."""

    config_entry: SenseConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SenseConfigEntry,
        gateway: ASyncSenseable,
        name: str,
        update: int | None,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=f"Sense {name} {gateway.sense_monitor_id}",
            update_interval=timedelta(seconds=update) if update else None,
        )
        self._gateway = gateway
        self.last_update_success = False


class SenseTrendCoordinator(SenseCoordinator):
    """Sense Trend Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SenseConfigEntry,
        gateway: ASyncSenseable,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, gateway, "Trends", None)
        self._statistics = SenseStatistics(hass, gateway)

    @override
    async def _async_update_data(self) -> None:
        """Update the trend data and the hourly statistics derived from it."""
        try:
            await self._gateway.update_trend_data()
        except (SenseAuthenticationException, SenseMFARequiredException) as err:
            _LOGGER.warning("Sense authentication expired")
            raise ConfigEntryAuthFailed(err) from err
        except SENSE_CONNECT_EXCEPTIONS as err:
            raise UpdateFailed(err) from err

        try:
            await self._statistics.async_import()
        except (SenseAuthenticationException, SenseMFARequiredException) as err:
            _LOGGER.debug("Sense authentication expired during statistics import")
            raise ConfigEntryAuthFailed(err) from err
        except SENSE_CONNECT_EXCEPTIONS as err:
            _LOGGER.debug("Unable to import Sense statistics: %s", err)
            raise UpdateFailed(err) from err

    async def async_import_provisional_hour(self) -> None:
        """Import the newest completed hour from its last in-progress reading."""
        await self._statistics.async_import_provisional()


class SenseRealtimeCoordinator(SenseCoordinator):
    """Sense Realtime Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SenseConfigEntry,
        gateway: ASyncSenseable,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, gateway, "Realtime", ACTIVE_UPDATE_RATE)

    @override
    async def _async_update_data(self) -> None:
        """Retrieve latest state."""
        try:
            await self._gateway.update_realtime()
        except SENSE_TIMEOUT_EXCEPTIONS as ex:
            raise UpdateFailed(f"Timeout retrieving realtime data: {ex}") from ex
        except SENSE_WEBSOCKET_EXCEPTIONS as ex:
            raise UpdateFailed(f"Failed to update realtime data: {ex}") from ex
        except SenseAPIException as ex:
            raise UpdateFailed(f"API error retrieving realtime data: {ex}") from ex
