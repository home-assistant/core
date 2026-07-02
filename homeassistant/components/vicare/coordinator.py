"""DataUpdateCoordinator for the ViCare integration."""

from datetime import timedelta
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareUtils import (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidCredentialsError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_CACHE_DURATION, DOMAIN
from .types import ViCareConfigEntry

_LOGGER = logging.getLogger(__name__)


class ViCareCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for a single ViCare device.

    Triggers a fresh fetch of the device's full feature payload into
    PyViCare's internal cache so entity ``value_getter`` lambdas read
    fresh data on each tick. Carries no payload of its own; freshness
    is signalled via ``last_update_success``.
    """

    config_entry: ViCareConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ViCareConfigEntry,
        device: PyViCareDevice,
        device_count: int,
    ) -> None:
        """Initialise the coordinator for one device."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{device.service.accessor.id}",
            update_interval=timedelta(seconds=DEFAULT_CACHE_DURATION * device_count),
        )
        self._device = device

    async def _async_update_data(self) -> None:
        """Refresh the device's feature payload."""
        await self.hass.async_add_executor_job(self._refresh)

    def _refresh(self) -> None:
        """Force a fresh fetch from the Viessmann API."""
        try:
            self._device.service.clear_cache()
            self._device.service.fetch_all_features()
        except PyViCareInvalidCredentialsError as err:
            raise ConfigEntryAuthFailed from err
        except (
            PyViCareDeviceCommunicationError,
            PyViCareRateLimitError,
            PyViCareInternalServerError,
            requests.RequestException,
        ) as err:
            raise UpdateFailed(str(err)) from err
