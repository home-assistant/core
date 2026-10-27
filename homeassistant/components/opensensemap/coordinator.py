"""Data update coordinator for the openSenseMap integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import NamedTuple, override

from opensensemap_api import _TITLES, OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(minutes=10)

# Stations report the same phenomenon in different units, but the library
# exposes only values. These map a station's reported unit (normalized to
# lowercase) to the matching Home Assistant unit so values convert correctly.
TEMPERATURE_UNITS: dict[str, str] = {
    "°c": UnitOfTemperature.CELSIUS,
    "c": UnitOfTemperature.CELSIUS,
    "°f": UnitOfTemperature.FAHRENHEIT,
    "f": UnitOfTemperature.FAHRENHEIT,
}
WIND_SPEED_UNITS: dict[str, str] = {
    "m/s": UnitOfSpeed.METERS_PER_SECOND,
    "km/h": UnitOfSpeed.KILOMETERS_PER_HOUR,
    "mph": UnitOfSpeed.MILES_PER_HOUR,
}
PRESSURE_UNITS: dict[str, str] = {
    "hpa": UnitOfPressure.HPA,
    "pa": UnitOfPressure.PA,
    "pascal": UnitOfPressure.PA,
    "mbar": UnitOfPressure.MBAR,
    "kpa": UnitOfPressure.KPA,
}


class Measurement(NamedTuple):
    """A station measurement paired with its detected unit, if any."""

    value: float | None
    unit: str | None = None


@dataclass(slots=True, frozen=True)
class OpenSenseMapStationData:
    """Immutable measurements for an openSenseMap station."""

    pm2_5: Measurement
    pm10: Measurement
    pm1_0: Measurement
    temperature: Measurement
    humidity: Measurement
    air_pressure: Measurement
    illuminance: Measurement
    wind_speed: Measurement
    wind_direction: Measurement


def _detect_unit(
    api: OpenSenseMap, title_key: str, unit_map: dict[str, str]
) -> str | None:
    """Return the Home Assistant unit for a phenomenon reported by the station."""

    # The library resolves a measurement by matching localized sensor titles
    # (opensensemap_api._TITLES) and returns the first matching sensor that has a
    # value. Mirror that approach to find the matching unit.
    for title in (*_TITLES.get(title_key, ()), title_key):
        for sensor in api.data.get("sensors", []):
            measurement = sensor.get("lastMeasurement") or {}
            if (
                sensor.get("title", "").casefold() == title.casefold()
                and measurement.get("value") is not None
            ):
                return unit_map.get((sensor.get("unit") or "").strip().casefold())
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

    @override
    async def _async_update_data(self) -> OpenSenseMapStationData:
        """Fetch latest data from the openSenseMap API."""
        try:
            await self.api.get_data()
        except OpenSenseMapError as err:
            raise UpdateFailed(
                f"Unable to fetch data from openSenseMap: {err}"
            ) from err
        return OpenSenseMapStationData(
            pm2_5=Measurement(self.api.pm2_5),
            pm10=Measurement(self.api.pm10),
            pm1_0=Measurement(self.api.pm1_0),
            temperature=Measurement(
                self.api.temperature,
                _detect_unit(self.api, "Temperature", TEMPERATURE_UNITS),
            ),
            humidity=Measurement(self.api.humidity),
            air_pressure=Measurement(
                self.api.air_pressure,
                _detect_unit(self.api, "Air Pressure", PRESSURE_UNITS),
            ),
            illuminance=Measurement(self.api.illuminance),
            wind_speed=Measurement(
                self.api.wind_speed,
                _detect_unit(self.api, "Wind Speed", WIND_SPEED_UNITS),
            ),
            wind_direction=Measurement(self.api.wind_direction),
        )
