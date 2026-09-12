"""BIOCAT device data update coordinators."""

from asyncio import CancelledError, timeout
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from httpx import HTTPStatusError, RequestError
from pyocat import (
    AsyncApiClient,
    WTCApiDisabledError,
    WTCApiTemporaryError,
    WTCApiUnauthorizedError,
)
from pyocat.models import MeasurementResponse, StateResponse

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import WatercrystConfigEntry

_LOGGER = logging.getLogger(__name__)


STATE_POLLING_INTERVAL = timedelta(seconds=30)
MEASUREMENTS_POLLING_INTERVAL = timedelta(seconds=60)


class WatercrystDataUpdateCoordinator[DataT](DataUpdateCoordinator[DataT]):
    """Base coordinator for WATERCryst BIOCAT Smart Home API."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        update_interval: timedelta,
        config_entry: WatercrystConfigEntry,
        client: AsyncApiClient,
    ) -> None:
        """Initializes the state data updater."""
        super().__init__(
            hass=hass,
            logger=logger,
            name=name,
            config_entry=config_entry,
            update_interval=update_interval,
            always_update=False,
        )
        self._client = client

    @override
    async def _async_update_data(self) -> DataT:
        try:
            async with timeout(10):
                return await self._async_fetch_data()
        except CancelledError:
            raise
        except (
            WTCApiDisabledError,
            WTCApiTemporaryError,
            HTTPStatusError,
            RequestError,
            TimeoutError,
        ) as err:
            raise UpdateFailed(f"Failed to update {self.name}", retry_after=60) from err
        except WTCApiUnauthorizedError as err:
            raise ConfigEntryAuthFailed(
                f"Failed to update {self.name}, unauthorized"
            ) from err

    async def _async_fetch_data(self) -> DataT:
        """Fetch data from API."""
        raise NotImplementedError


class WatercrystStateUpdateCoordinator(WatercrystDataUpdateCoordinator[StateResponse]):
    """State data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WatercrystConfigEntry,
        client: AsyncApiClient,
    ) -> None:
        """Initializes the state data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_state",
            update_interval=STATE_POLLING_INTERVAL,
            config_entry=config_entry,
            client=client,
        )

    @override
    async def _async_fetch_data(self) -> StateResponse:
        lang = self.hass.config.language.split("-")[0]
        locale = lang if lang in {"cs", "da", "de", "en", "es"} else "en"
        return await self._client.get_state(locale=locale)


class WatercrystMeasurementsUpdateCoordinator(
    WatercrystDataUpdateCoordinator[MeasurementResponse]
):
    """Measurements data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WatercrystConfigEntry,
        client: AsyncApiClient,
        state: WatercrystStateUpdateCoordinator,
    ) -> None:
        """Initializes the measurement data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_measurements",
            update_interval=MEASUREMENTS_POLLING_INTERVAL,
            config_entry=config_entry,
            client=client,
        )
        self._state = state

    @override
    async def _async_fetch_data(self) -> MeasurementResponse:
        if self._state.data is None or not self._state.data.online:
            raise UpdateFailed("Failed to update measurements", retry_after=60)
        return await self._client.get_measurements()
