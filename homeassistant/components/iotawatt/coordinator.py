"""IoTaWatt DataUpdateCoordinator."""

from datetime import timedelta
import logging
from typing import override

from iotawattpy.iotawatt import Iotawatt

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LEGACY_ENERGY, CONNECTION_ERRORS

_LOGGER = logging.getLogger(__name__)

# Matches iotwatt data log interval
REQUEST_REFRESH_DEFAULT_COOLDOWN = 5

type IotawattConfigEntry = ConfigEntry[IotawattUpdater]


class IotawattUpdater(DataUpdateCoordinator):
    """Class to manage fetching update data from the IoTaWatt Energy Device."""

    api: Iotawatt | None = None
    config_entry: IotawattConfigEntry

    def __init__(self, hass: HomeAssistant, entry: IotawattConfigEntry) -> None:
        """Initialize IotaWattUpdater object."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REQUEST_REFRESH_DEFAULT_COOLDOWN,
                immediate=True,
            ),
        )

    @override
    async def _async_update_data(self):
        """Fetch sensors from IoTaWatt device."""
        if self.api is None:
            api = Iotawatt(
                self.config_entry.title,
                self.config_entry.data[CONF_HOST],
                httpx_client.get_async_client(self.hass),
                self.config_entry.data.get(CONF_USERNAME),
                self.config_entry.data.get(CONF_PASSWORD),
                integratedInterval="d",
                includeNonTotalSensors=False,
                includeLifetimeSensors=True,
                includeTotalSensors=self.config_entry.options.get(
                    CONF_LEGACY_ENERGY, True
                ),
            )
            try:
                is_authenticated = await api.connect()
            except CONNECTION_ERRORS as err:
                raise UpdateFailed("Connection failed") from err

            if not is_authenticated:
                raise UpdateFailed("Authentication error")

            self.api = api

        try:
            await self.api.update()
        except CONNECTION_ERRORS as err:
            raise UpdateFailed("Connection failed") from err
        return self.api.getSensors()
