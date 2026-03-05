"""DataUpdateCoordinator for the PECO Outage Counter integration."""

from dataclasses import dataclass
from datetime import timedelta

from peco import (
    AlertResults,
    BadJSONError,
    HttpError,
    OutageResults,
    PecoOutageApi,
    UnresponsiveMeterError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_COUNTY, LOGGER, OUTAGE_SCAN_INTERVAL, SMART_METER_SCAN_INTERVAL


@dataclass
class PECOCoordinatorData:
    """Data class to hold PECO outage and alert results."""

    outages: OutageResults
    alerts: AlertResults


class PecoOutageCoordinator(DataUpdateCoordinator[PECOCoordinatorData]):
    """Coordinator for PECO outage data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the outage coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="PECO Outage Count",
            update_interval=timedelta(minutes=OUTAGE_SCAN_INTERVAL),
        )
        self._api = PecoOutageApi()
        self._websession = async_get_clientsession(hass)
        self._county: str = entry.data[CONF_COUNTY]

    async def _async_update_data(self) -> PECOCoordinatorData:
        """Fetch data from API."""
        try:
            outages = (
                await self._api.get_outage_totals(self._websession)
                if self._county == "TOTAL"
                else await self._api.get_outage_count(self._county, self._websession)
            )
            alerts = await self._api.get_map_alerts(self._websession)
        except HttpError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        except BadJSONError as err:
            raise UpdateFailed(f"Error parsing data: {err}") from err
        return PECOCoordinatorData(outages, alerts)


class PecoSmartMeterCoordinator(DataUpdateCoordinator[bool]):
    """Coordinator for PECO smart meter data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, phone_number: str
    ) -> None:
        """Initialize the smart meter coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="PECO Smart Meter",
            update_interval=timedelta(minutes=SMART_METER_SCAN_INTERVAL),
        )
        self._api = PecoOutageApi()
        self._websession = async_get_clientsession(hass)
        self._phone_number = phone_number

    async def _async_update_data(self) -> bool:
        """Fetch data from API."""
        try:
            data = await self._api.meter_check(self._phone_number, self._websession)
        except UnresponsiveMeterError as err:
            raise UpdateFailed("Unresponsive meter") from err
        except HttpError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        except BadJSONError as err:
            raise UpdateFailed(f"Error parsing data: {err}") from err
        return data
