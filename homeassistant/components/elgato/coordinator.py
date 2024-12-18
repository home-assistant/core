"""DataUpdateCoordinator for Elgato."""

from dataclasses import dataclass

from elgato import BatteryInfo, Elgato, ElgatoConnectionError, Info, Settings, State

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type ElgatoConfigEntry = ConfigEntry[ElgatoDataUpdateCoordinator]


@dataclass
class ElgatoData:
    """Elgato data stored in the DataUpdateCoordinator."""

    battery: BatteryInfo | None
    info: Info
    settings: Settings
    state: State


class ElgatoDataUpdateCoordinator(DataUpdateCoordinator[ElgatoData]):
    """Class to manage fetching Elgato data."""

    config_entry: ElgatoConfigEntry
    has_battery: bool | None = None

    def __init__(self, hass: HomeAssistant, entry: ElgatoConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry = entry
        self.client = Elgato(
            entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
        )
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> ElgatoData:
        """Fetch data from the Elgato device."""
        try:
            if self.has_battery is None:
                self.has_battery = await self.client.has_battery()

            return ElgatoData(
                battery=await self.client.battery() if self.has_battery else None,
                info=await self.client.info(),
                settings=await self.client.settings(),
                state=await self.client.state(),
            )
        except ElgatoConnectionError as err:
            raise UpdateFailed(err) from err
