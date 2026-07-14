"""BIOCAT device data update coordinators."""

from asyncio import timeout
from datetime import timedelta
import logging
from typing import override

from pyocat import AsyncApiClient
from pyocat.models import MeasurementResponse, StateResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class MeasurementsUpdateCoordinator(DataUpdateCoordinator[MeasurementResponse]):
    """Measurements data updater coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AsyncApiClient,
    ) -> None:
        """Initializes the measurement data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Measurements update coordinator",
            config_entry=entry,
            update_interval=timedelta(seconds=60),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners.
            always_update=False,
        )
        self._client = client

    @override
    async def _async_update_data(self):
        try:
            async with timeout(10):
                return await self._client.get_measurements()
        except Exception as err:
            _LOGGER.exception("Failed to update measurements")
            raise UpdateFailed(retry_after=60) from err


class StateUpdateCoordinator(DataUpdateCoordinator[StateResponse]):
    """State data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: AsyncApiClient,
    ) -> None:
        """Initializes the state data updater."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="State update coordinator",
            config_entry=entry,
            update_interval=timedelta(seconds=30),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners.
            always_update=False,
        )
        self._client = client

    @override
    async def _async_update_data(self):
        try:
            async with timeout(10):
                return await self._client.get_state(locale=self.hass.config.language)
        except Exception as err:
            _LOGGER.exception("Failed to update state")
            raise UpdateFailed(retry_after=60) from err
