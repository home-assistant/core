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

if TYPE_CHECKING:
    from . import WatercrystConfigEntry

_LOGGER = logging.getLogger(__name__)


class StateUpdateCoordinator(DataUpdateCoordinator[StateResponse]):
    """State data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WatercrystConfigEntry,
        client: AsyncApiClient,
    ) -> None:
        """Initializes the state data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="State update coordinator",
            config_entry=entry,
            update_interval=timedelta(seconds=30),
            always_update=False,
        )
        self._client = client

    @override
    async def _async_update_data(self):
        try:
            async with timeout(10):
                lang = self.hass.config.language.split("-")[0]
                locale = lang if lang in {"cs", "da", "de", "en", "es"} else "en"
                return await self._client.get_state(locale=locale)
        except CancelledError:
            raise
        except (
            WTCApiDisabledError,
            WTCApiTemporaryError,
            HTTPStatusError,
            RequestError,
            TimeoutError,
        ) as err:
            raise UpdateFailed("Failed to update state", retry_after=60) from err
        except WTCApiUnauthorizedError as err:
            raise ConfigEntryAuthFailed("Failed to update state, unauthorized") from err


class MeasurementsUpdateCoordinator(DataUpdateCoordinator[MeasurementResponse]):
    """Measurements data updater coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: WatercrystConfigEntry,
        client: AsyncApiClient,
        state: StateUpdateCoordinator,
    ) -> None:
        """Initializes the measurement data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Measurements update coordinator",
            config_entry=entry,
            update_interval=timedelta(seconds=60),
            always_update=False,
        )
        self._client = client
        self._state = state

    @override
    async def _async_update_data(self) -> MeasurementResponse | None:
        if self._state.data is None or not self._state.data.online:
            return self.data
        try:
            async with timeout(10):
                return await self._client.get_measurements()
        except (
            WTCApiDisabledError,
            WTCApiTemporaryError,
            HTTPStatusError,
            RequestError,
            TimeoutError,
        ) as err:
            raise UpdateFailed("Failed to update measurements", retry_after=60) from err
        except WTCApiUnauthorizedError as err:
            raise ConfigEntryAuthFailed(
                "Failed to update measurements, unauthorized"
            ) from err
