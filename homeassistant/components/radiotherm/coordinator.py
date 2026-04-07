"""Coordinator for radiotherm."""

from __future__ import annotations

from datetime import timedelta
import logging
from urllib.error import URLError

from radiotherm.validate import RadiothermTstatError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .data import RadioThermInitData, RadioThermUpdate, async_get_data

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=15)


class RadioThermUpdateCoordinator(DataUpdateCoordinator[RadioThermUpdate]):
    """DataUpdateCoordinator to gather data for radio thermostats."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        init_data: RadioThermInitData,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        self.init_data = init_data
        self._description = f"{init_data.name} ({init_data.host})"
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"radiotherm {self.init_data.name}",
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> RadioThermUpdate:
        """Update data from the thermostat."""
        try:
            return await async_get_data(self.hass, self.init_data.tstat)
        except RadiothermTstatError as ex:
            _LOGGER.warning(
                "%s was busy (invalid value returned): %s", self._description, ex
            )
        except TimeoutError as ex:
            _LOGGER.warning(
                "%s timed out waiting for a response: %s", self._description, ex
            )
        except (OSError, URLError) as ex:
            _LOGGER.error("%s connection error: %s", self._description, ex)

        # If an error was raised, then pass the current state back.
        return self.data
