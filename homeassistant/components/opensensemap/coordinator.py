"""Data update coordinator for the openSenseMap integration."""

from dataclasses import dataclass
from datetime import timedelta

from opensensemap_api import _TITLES, OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(minutes=10)

TEMPERATURE_UNITS: dict[str, str] = {
    "°C": UnitOfTemperature.CELSIUS,
    "C": UnitOfTemperature.CELSIUS,
    "°F": UnitOfTemperature.FAHRENHEIT,
    "F": UnitOfTemperature.FAHRENHEIT,
}


@dataclass(slots=True, frozen=True)
class OpenSenseMapStationData:
    """Immutable measurements for an openSenseMap station."""

    pm2_5: float | None
    pm10: float | None
    pm1_0: float | None
    temperature: float | None
    temperature_unit: str | None
    humidity: float | None
    air_pressure: float | None
    illuminance: float | None
    uv: float | None
    wind_speed: float | None
    wind_direction: float | None
    precipitation: float | None


def _detect_temperature_unit(api: OpenSenseMap) -> str | None:
    """Return the temperature unit reported by the station, if known."""
    # The library resolves a measurement by matching localized sensor titles
    # (opensensemap_api._TITLES) and exposes only its value, not the unit.
    # Walk the same titles to find that sensor and read its unit.
    for title in (*_TITLES["Temperature"], "Temperature"):
        for sensor in api.data.get("sensors", []):
            if sensor.get("title", "").casefold() == title.casefold():
                return TEMPERATURE_UNITS.get(sensor.get("unit"))
    return None


type OpenSenseMapConfigEntry = ConfigEntry[OpenSenseMapCoordinator]


class OpenSenseMapCoordinator(DataUpdateCoordinator[OpenSenseMapStationData]):
    """Coordinator to manage data updates for an openSenseMap station."""

    config_entry: OpenSenseMapConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenSenseMapConfigEntry,
        api: OpenSenseMap,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> OpenSenseMapStationData:
        """Fetch latest data from the openSenseMap API."""
        try:
            await self.api.get_data()
        except OpenSenseMapError as err:
            raise UpdateFailed(
                f"Unable to fetch data from openSenseMap: {err}"
            ) from err
        return OpenSenseMapStationData(
            pm2_5=self.api.pm2_5,
            pm10=self.api.pm10,
            pm1_0=self.api.pm1_0,
            temperature=self.api.temperature,
            temperature_unit=_detect_temperature_unit(self.api),
            humidity=self.api.humidity,
            air_pressure=self.api.air_pressure,
            illuminance=self.api.illuminance,
            uv=self.api.uv,
            wind_speed=self.api.wind_speed,
            wind_direction=self.api.wind_direction,
            precipitation=self.api.precipitation,
        )
