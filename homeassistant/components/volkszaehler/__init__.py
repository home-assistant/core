"""The volkszaehler component."""

from datetime import timedelta
import logging

from volkszaehler import Volkszaehler
from volkszaehler.exceptions import VolkszaehlerApiConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_UUID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import Throttle

from .const import SUBENTRY_TYPE_CHANNEL

_PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)


type VolkszaehlerConfigEntry = ConfigEntry[dict[str, VolkszaehlerData]]


class VolkszaehlerData:
    """The class for handling the data retrieval from the Volkszaehler API."""

    def __init__(self, api: Volkszaehler) -> None:
        """Initialize the data object."""
        self.api = api
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Get the latest data from the Volkszaehler REST API."""

        try:
            await self.api.get_data()
            self.available = True
        except VolkszaehlerApiConnectionError:
            _LOGGER.error("Unable to fetch data from the Volkszaehler API")
            self.available = False


async def async_setup_entry(
    hass: HomeAssistant, entry: VolkszaehlerConfigEntry
) -> bool:
    """Set up Volkszaehler from a config entry."""
    runtime_data: dict[str, VolkszaehlerData] = {}

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_CHANNEL):
        vz_data = VolkszaehlerData(
            Volkszaehler(
                async_get_clientsession(hass),
                subentry.data[CONF_UUID],
                host=entry.data[CONF_HOST],
                port=entry.data[CONF_PORT],
                middleware=False,
            )
        )
        await vz_data.async_update()
        if not vz_data.available or vz_data.api.data is None:
            raise ConfigEntryNotReady(
                "Unable to fetch initial data from the Volkszaehler API"
            )

        runtime_data[subentry.subentry_id] = vz_data

    entry.runtime_data = runtime_data
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: VolkszaehlerConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
