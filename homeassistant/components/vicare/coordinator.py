"""DataUpdateCoordinator for the ViCare integration."""

from datetime import timedelta
import logging

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareService import ViCareDeviceAccessor
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
    """Coordinator for a single ViCare gateway.

    In viaGateway mode all devices behind a gateway share one service, so a
    single feature fetch refreshes every device on that gateway. The fetch runs
    against a representative device using its accessor (the shared service is
    stateless and needs the accessor per call); freshness is signalled via
    ``last_update_success``. Carries no payload of its own.
    """

    config_entry: ViCareConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ViCareConfigEntry,
        device: PyViCareDevice,
        accessor: ViCareDeviceAccessor,
        gateway_count: int,
    ) -> None:
        """Initialise the coordinator for one gateway."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{accessor.serial}",
            update_interval=timedelta(seconds=DEFAULT_CACHE_DURATION * gateway_count),
        )
        self._device = device
        self._accessor = accessor

    async def _async_update_data(self) -> None:
        """Refresh the gateway's feature payload."""
        await self.hass.async_add_executor_job(self._refresh)

    def _refresh(self) -> None:
        """Force a fresh fetch from the Viessmann API."""
        try:
            self._device.service.clear_cache()
            self._device.service.fetch_all_features(self._accessor)
        except PyViCareInvalidCredentialsError as err:
            raise ConfigEntryAuthFailed from err
        except (
            PyViCareDeviceCommunicationError,
            PyViCareRateLimitError,
            PyViCareInternalServerError,
            requests.RequestException,
        ) as err:
            raise UpdateFailed(str(err)) from err
