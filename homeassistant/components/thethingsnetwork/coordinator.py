"""The Things Network's integration DataUpdateCoordinator."""

from datetime import timedelta
import logging

from ttn_client import TTNAuthError, TTNClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_APP_ID, POLLING_PERIOD_S

_LOGGER = logging.getLogger(__name__)


class TTNCoordinator(DataUpdateCoordinator[TTNClient.DATA_TYPE]):
    """TTN coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            # Name of the data. For logging purposes.
            name=f"TheThingsNetwork_{entry.data[CONF_APP_ID]}",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(
                seconds=POLLING_PERIOD_S,
            ),
        )

        self._client = TTNClient(
            entry.data[CONF_HOST],
            entry.data[CONF_APP_ID],
            entry.data[CONF_API_KEY],
            push_callback=self._push_callback,
        )

    async def _async_update_data(self) -> TTNClient.DATA_TYPE:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            measurements = await self._client.fetch_data()
        except TTNAuthError as err:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            _LOGGER.error("TTNAuthError")
            raise ConfigEntryAuthFailed from err
        else:
            # Return measurements
            _LOGGER.debug("fetched data: %s", measurements)
            return measurements

    async def _push_callback(self, data: TTNClient.DATA_TYPE) -> None:
        _LOGGER.debug("pushed data: %s", data)

        # Push data to entities
        self.async_set_updated_data(data)
