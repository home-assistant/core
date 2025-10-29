"""Coordinator for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pysaunum import SaunumClient, SaunumData, SaunumException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LeilSaunaCoordinator(DataUpdateCoordinator[SaunumData]):
    """Coordinator for fetching Saunum Leil Sauna data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SaunumClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=config_entry,
        )
        self.client = client
        # Track whether we have already logged that the device is unavailable.
        # We log a single INFO message when the device first becomes unavailable
        # and another INFO message when communication is restored, per HA
        # unavailability logging guidelines.
        self._unavailable_logged: bool = False

    async def _async_update_data(self) -> SaunumData:
        """Fetch data from the sauna controller."""
        try:
            data = await self.client.async_get_data()
        except SaunumException as err:
            if not self._unavailable_logged:
                _LOGGER.info("Device became unavailable: %s", err)
                self._unavailable_logged = True
            raise UpdateFailed(f"communication error: {err}") from err
        else:
            if self._unavailable_logged:
                _LOGGER.info("Device communication restored")
                self._unavailable_logged = False
            return data

    async def async_start_session(self) -> bool:
        """Start a sauna session."""
        try:
            await self.client.async_start_session()
            self.async_set_updated_data(await self.client.async_get_data())
        except SaunumException as err:
            _LOGGER.error("Error starting session: %s", err)
            return False
        else:
            return True

    async def async_stop_session(self) -> bool:
        """Stop the sauna session."""
        try:
            await self.client.async_stop_session()
            self.async_set_updated_data(await self.client.async_get_data())
        except SaunumException as err:
            _LOGGER.error("Error stopping session: %s", err)
            return False
        else:
            return True

    async def async_set_target_temperature(self, temperature: int) -> bool:
        """Set the target temperature in Celsius."""
        try:
            await self.client.async_set_target_temperature(temperature)
            self.async_set_updated_data(await self.client.async_get_data())
        except (ValueError, SaunumException) as err:
            _LOGGER.error("Error setting target temperature: %s", err)
            return False
        else:
            return True
