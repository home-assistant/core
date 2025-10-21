"""Data update coordinator for eGauge energy monitors."""

from __future__ import annotations

from datetime import timedelta

from egauge_async.json import (
    EgaugeAuthenticationError,
    EgaugeConnectionError,
    EgaugeJsonClient,
    EgaugeParsingException,
    RegisterInfo,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER
from .models import EgaugeData


class EgaugeDataCoordinator(DataUpdateCoordinator[EgaugeData]):
    """Class to manage fetching eGauge data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: EgaugeJsonClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
            config_entry=config_entry,
        )
        self.client = client
        # Populated on first refresh
        self.serial_number: str
        self.hostname: str
        self._register_info: dict[str, RegisterInfo] | None = None

    async def _async_update_data(self) -> EgaugeData:
        """Fetch data from eGauge device."""
        # First time only: fetch static device info
        if self._register_info is None:
            try:
                self.serial_number = await self.client.get_device_serial_number()
                self.hostname = await self.client.get_hostname()
                self._register_info = await self.client.get_register_info()
            except EgaugeAuthenticationError as err:
                raise ConfigEntryAuthFailed from err
            except (EgaugeConnectionError, EgaugeParsingException) as err:
                raise UpdateFailed(f"Error fetching device info: {err}") from err

        # Every time: fetch dynamic measurements
        try:
            measurements = await self.client.get_current_measurements()
            counters = await self.client.get_current_counters()
        except EgaugeAuthenticationError as err:
            raise ConfigEntryAuthFailed from err
        except (EgaugeConnectionError, EgaugeParsingException) as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        return EgaugeData(
            measurements=measurements,
            counters=counters,
            register_info=self._register_info,
        )
