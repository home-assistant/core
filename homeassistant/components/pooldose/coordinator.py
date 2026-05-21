"""Data update coordinator for the PoolDose integration."""

from datetime import timedelta
import logging

from pooldose.client import PooldoseClient
from pooldose.request_status import RequestStatus
from pooldose.type_definitions import DeviceInfoDict, StructuredValuesDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

type PooldoseConfigEntry = ConfigEntry[PooldoseCoordinator]


class PooldoseCoordinator(DataUpdateCoordinator[StructuredValuesDict]):
    """Coordinator for PoolDose integration."""

    device_info: DeviceInfoDict
    config_entry: PooldoseConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: PooldoseClient,
        config_entry: PooldoseConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Pooldose",
            update_interval=timedelta(seconds=600),  # Default update interval
            config_entry=config_entry,
        )
        self.client = client

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        # Update device info after successful connection
        self.device_info = self.client.device_info
        _LOGGER.debug("Device info: %s", self.device_info)

    async def _async_update_data(self) -> StructuredValuesDict:
        """Fetch data from the PoolDose API."""
        try:
            status, instant_values = await self.client.instant_values_structured()
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=self.config_entry.domain,
                translation_key="update_timeout",
            ) from err
        except (ConnectionError, OSError) as err:
            raise UpdateFailed(
                translation_domain=self.config_entry.domain,
                translation_key="update_connect_failed",
            ) from err

        if status != RequestStatus.SUCCESS:
            raise UpdateFailed(
                translation_domain=self.config_entry.domain,
                translation_key="api_status_error",
                translation_placeholders={"status": str(status.value)},
            )

        if not instant_values:
            raise UpdateFailed(
                translation_domain=self.config_entry.domain,
                translation_key="no_data_received",
            )

        _LOGGER.debug("Instant values structured: %s", instant_values)
        return instant_values
