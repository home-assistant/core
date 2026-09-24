"""DataUpdateCoordinator for the ViCare integration."""

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

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_CACHE_DURATION, DOMAIN
from .types import ViCareConfigEntry
from .utils import retry_after_from

_LOGGER = logging.getLogger(__name__)


BACKOFF_STEPS = (300, 600, 900)  # 5min, 10min, 15min


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
        self._consecutive_offline_failures: int = 0

    @override
    async def _async_update_data(self) -> None:
        """Refresh the gateway's feature payload."""
        await self.hass.async_add_executor_job(self._refresh)

    def _refresh(self) -> None:
        """Force a fresh fetch from the Viessmann API."""
        try:
            self._device.service.clear_cache()
            self._device.service.fetch_all_features(self._accessor)
            self._consecutive_offline_failures = 0
        except PyViCareNotSupportedFeatureError:
            # PACKAGE_NOT_PAID_FOR: load with no features instead of retrying setup.
            _LOGGER.debug(
                "No accessible features for gateway %s", self._accessor.serial
            )
            self._consecutive_offline_failures = 0
        except PyViCareInvalidCredentialsError as err:
            raise ConfigEntryAuthFailed from err
        except PyViCareRateLimitError as err:
            raise UpdateFailed(
                str(err),
                retry_after=retry_after_from(
                    err,
                    self.update_interval or timedelta(seconds=DEFAULT_CACHE_DURATION),
                ),
            ) from err
        except PyViCareDeviceCommunicationError as err:
            error_str = str(err)
            if (
                getattr(err, "reason", None) == "GATEWAY_OFFLINE"
                or "GATEWAY_OFFLINE" in error_str
            ):
                self._consecutive_offline_failures += 1
                idx = min(
                    self._consecutive_offline_failures - 1,
                    len(BACKOFF_STEPS) - 1,
                )
                normal_interval = int(
                    (
                        self.update_interval
                        or timedelta(seconds=DEFAULT_CACHE_DURATION)
                    ).total_seconds()
                )
                backoff = max(BACKOFF_STEPS[idx], normal_interval)
                _LOGGER.debug(
                    "ViCare gateway %s is offline (consecutive failures: %d). "
                    "Backing off next refresh for %d seconds",
                    self._accessor.serial,
                    self._consecutive_offline_failures,
                    backoff,
                )
                raise UpdateFailed(
                    error_str,
                    retry_after=backoff,
                ) from err
            raise UpdateFailed(error_str) from err
        except (
            PyViCareInternalServerError,
            PyViCareInvalidDataError,
            requests.RequestException,
        ) as err:
            raise UpdateFailed(str(err)) from err
