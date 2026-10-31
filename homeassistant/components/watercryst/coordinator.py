"""BIOCAT device data update coordinators."""

from abc import abstractmethod
from asyncio import CancelledError
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from httpx2 import HTTPStatusError, RequestError
from pyocat import (
    AsyncApiClient,
    WTCApiDisabledError,
    WTCApiTemporaryError,
    WTCApiUnauthorizedError,
)
from pyocat.models import DeviceResponse, MeasurementResponse, StateResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import WatercrystConfigEntry

_LOGGER = logging.getLogger(__name__)

DEVICE_INFO_POLLING_INTERVAL = timedelta(hours=24)
STATE_POLLING_INTERVAL = timedelta(seconds=30)
MEASUREMENTS_POLLING_INTERVAL = timedelta(seconds=60)


class WatercrystBaseCoordinator[DataT](DataUpdateCoordinator[DataT]):
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
        """Initializes the base data update coordinator."""
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
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "coordinator_name": self.name,
                    "error_name": type(err).__name__,
                    "error": str(err),
                },
                retry_after=60,
            ) from err
        except WTCApiUnauthorizedError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed_unauthorized",
                translation_placeholders={
                    "coordinator_name": self.name,
                },
            ) from err

    @abstractmethod
    async def _async_fetch_data(self) -> DataT:
        """Fetch data from API."""


class WatercrystStateCoordinator(WatercrystBaseCoordinator[StateResponse]):
    """State data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WatercrystConfigEntry,
        client: AsyncApiClient,
    ) -> None:
        """Initializes the state data update coordinator."""
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


class WatercrystMeasurementsCoordinator(WatercrystBaseCoordinator[MeasurementResponse]):
    """Measurements data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WatercrystConfigEntry,
        client: AsyncApiClient,
    ) -> None:
        """Initializes the measurement data update coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_measurements",
            update_interval=MEASUREMENTS_POLLING_INTERVAL,
            config_entry=config_entry,
            client=client,
        )

    @override
    async def _async_fetch_data(self) -> MeasurementResponse:
        return await self._client.get_measurements()


class WatercrystUpdateCoordinator(WatercrystBaseCoordinator[DeviceResponse]):
    """Watercryst update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WatercrystConfigEntry,
        client: AsyncApiClient,
        state: WatercrystStateCoordinator,
        measurements: WatercrystMeasurementsCoordinator,
    ) -> None:
        """Initializes the data update coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_device_info",
            update_interval=DEVICE_INFO_POLLING_INTERVAL,
            config_entry=config_entry,
            client=client,
        )
        self.state = state
        self.measurements = measurements

    @override
    async def _async_fetch_data(self) -> DeviceResponse:
        return await self._client.get_device_info()
