"""DataUpdateCoordinator for the aurora_abb_powerone integration."""

import logging
from time import sleep
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .aurora_client import AuroraClient, AuroraClientError, AuroraClientTimeoutError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


type AuroraAbbConfigEntry = ConfigEntry[AuroraAbbDataUpdateCoordinator]


class AuroraAbbDataUpdateCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Class to manage fetching AuroraAbbPowerone data."""

    client: AuroraClient

    available_prev: bool | None
    available: bool | None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: AuroraAbbConfigEntry,
        client: AuroraClient,
    ) -> None:
        """Initialize the data update coordinator."""

        self.client = client

        self.available_prev = None
        self.available = None

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _update_data(self) -> dict[str, Any]:
        """Fetch new state data for the sensors.

        This is the only function that should fetch new data for Home Assistant.
        """
        self.available_prev = self.available
        retries: int = 3
        data = {}
        while retries > 0:
            try:
                result = self.client.try_connect_and_fetch_data()
            except AuroraClientTimeoutError:
                self.available = False
                _LOGGER.debug("No response from inverter (could be dark)")
                retries = 0
            except AuroraClientError as error:
                self.available = False
                retries -= 1
                if retries <= 0:
                    raise UpdateFailed(error) from error
                _LOGGER.debug(
                    "Exception: %s occurred, %d retries remaining",
                    repr(error),
                    retries,
                )
                sleep(1)
            else:
                data = result.__dict__
                self.available = True
                retries = 0
            finally:
                if (self.available != self.available_prev) and (
                    self.available_prev is not None
                ):
                    if self.available:
                        _LOGGER.warning("Communication with %s back online", self.name)
                    else:
                        _LOGGER.warning(
                            "Communication with %s lost",
                            self.name,
                        )
        return data

    async def _async_update_data(self) -> dict[str, Any]:
        """Update inverter data in the executor."""
        return await self.hass.async_add_executor_job(self._update_data)
