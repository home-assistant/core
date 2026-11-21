"""BIOCAT device data update coordinators."""

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import override

from pyocat import (
    AsyncApiClient,
    WTCApiCancelledError,
    WTCApiDisabledError,
    WTCApiQuotaExceededError,
    WTCApiRequestError,
    WTCApiServerError,
    WTCApiTimeoutError,
    WTCApiUnauthorizedError,
    WTCApiValidationError,
)
from pyocat.models import DeviceResponse, MeasurementResponse, StateResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEVICE_INFO_POLLING_INTERVAL = timedelta(hours=24)
STATE_POLLING_INTERVAL = timedelta(seconds=30)
MEASUREMENTS_POLLING_INTERVAL = timedelta(seconds=60)
RETRY_INTERVAL = 60


type WatercrystConfigEntry = ConfigEntry[WatercrystUpdateCoordinator]


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
        except (
            WTCApiCancelledError,
            WTCApiQuotaExceededError,
            WTCApiRequestError,
            WTCApiServerError,
            WTCApiTimeoutError,
            WTCApiValidationError,
        ) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                retry_after=RETRY_INTERVAL,
            ) from err
        except WTCApiUnauthorizedError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="update_failed_unauthorized",
            ) from err
        except WTCApiDisabledError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="update_failed_api_disabled",
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
        return await self._client.get_state(locale="en")


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

        @callback
        def _handle_update() -> None:
            if not self.last_update_success:
                return
            registry = dr.async_get(hass)
            device = registry.async_get_device_by_identifier(
                identifier=(DOMAIN, self.data.biocat_serial),
                config_entry_id=config_entry.entry_id,
            )
            if device:
                registry.async_update_device(
                    device.id,
                    sw_version=self.data.current_firmware_version,
                    hw_version=self.data.current_hardware_version,
                    model=self.data.get_model_name(),
                    model_id=self.data.device_type_number,
                    name=self.data.name or config_entry.title,
                )

        config_entry.async_on_unload(self.async_add_listener(_handle_update))

    @override
    async def _async_fetch_data(self) -> DeviceResponse:
        return await self._client.get_device_info()
