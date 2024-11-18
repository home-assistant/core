"""IoTaWatt DataUpdateCoordinator."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from iotawattpy.iotawatt import Iotawatt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONNECTION_ERRORS

_LOGGER = logging.getLogger(__name__)

# Matches iotwatt data log interval
REQUEST_REFRESH_DEFAULT_COOLDOWN = 5


class IotawattUpdater(DataUpdateCoordinator):
    """Class to manage fetching update data from the IoTaWatt Energy Device."""

    api: Iotawatt | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize IotaWattUpdater object."""
        self.entry = entry
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=entry.title,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REQUEST_REFRESH_DEFAULT_COOLDOWN,
                immediate=True,
            ),
        )

        self._last_run: datetime | None = None

    def update_last_run(self, last_run: datetime) -> None:
        """Notify coordinator of a sensor last update time."""
        # We want to fetch the data from the iotawatt since HA was last shutdown.
        # We retrieve from the sensor last updated.
        # This method is called from each sensor upon their state being restored.
        if self._last_run is None or last_run > self._last_run:
            self._last_run = last_run

    async def _async_update_data(self):
        """Fetch sensors from IoTaWatt device."""
        if self.api is None:
            api = Iotawatt(
                self.entry.title,
                self.entry.data[CONF_HOST],
                httpx_client.get_async_client(self.hass),
                self.entry.data.get(CONF_USERNAME),
                self.entry.data.get(CONF_PASSWORD),
                integratedInterval="d",
                includeNonTotalSensors=False,
            )
            try:
                is_authenticated = await api.connect()
            except CONNECTION_ERRORS as err:
                raise UpdateFailed("Connection failed") from err

            if not is_authenticated:
                raise UpdateFailed("Authentication error")

            self.api = api

        await self.api.update(lastUpdate=self._last_run)
        self._last_run = None
        return self.api.getSensors()
