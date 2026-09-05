"""DataUpdateCoordinator for the ViCare integration."""

from collections.abc import Callable
from datetime import timedelta
import logging
from typing import override

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareService import ViCareDeviceAccessor
from PyViCare.PyViCareUtils import (
    PyViCareDeviceCommunicationError,
    PyViCareInternalServerError,
    PyViCareInvalidCredentialsError,
    PyViCareInvalidDataError,
    PyViCareNotSupportedFeatureError,
    PyViCareRateLimitError,
)
import requests

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_CACHE_DURATION, DOMAIN
from .types import ViCareConfigEntry

_LOGGER = logging.getLogger(__name__)


class ViCareCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for a single ViCare gateway.

    In viaGateway mode all devices behind a gateway share one service, so a
    single feature fetch refreshes every device on that gateway. The fetch takes
    the accessor of a representative device. Carries no payload of its own;
    freshness is signalled via ``last_update_success``.
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
        self._value_readers: list[Callable[[], None]] = []

    @callback
    def async_add_value_reader(self, reader: Callable[[], None]) -> Callable[[], None]:
        """Register a reader to run in the executor after each fetch."""
        self._value_readers.append(reader)

        def remove_value_reader() -> None:
            self._value_readers.remove(reader)

        return remove_value_reader

    @override
    async def _async_update_data(self) -> None:
        """Refresh the gateway's feature payload."""
        await self.hass.async_add_executor_job(self._refresh)

    def _refresh(self) -> None:
        """Force a fresh fetch from the Viessmann API."""
        try:
            self._device.service.clear_cache()
            self._device.service.fetch_all_features(self._accessor)
        except PyViCareNotSupportedFeatureError:
            # PACKAGE_NOT_PAID_FOR: load with no features instead of retrying setup.
            _LOGGER.debug(
                "No accessible features for gateway %s", self._accessor.serial
            )
        except PyViCareInvalidCredentialsError as err:
            raise ConfigEntryAuthFailed from err
        except (
            PyViCareDeviceCommunicationError,
            PyViCareInternalServerError,
            PyViCareInvalidDataError,
            PyViCareRateLimitError,
            requests.RequestException,
        ) as err:
            raise UpdateFailed(str(err)) from err
        else:
            # Only after a successful fetch: the cache was emptied above, and a
            # reader must not be the one to refill it from the event loop.
            # Iterate a copy, entities deregister from the event loop thread.
            for reader in list(self._value_readers):
                try:
                    reader()
                except Exception:
                    # One unreadable value must not take the whole device down.
                    _LOGGER.exception("Error reading a ViCare entity value")
