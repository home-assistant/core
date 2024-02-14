"""Accessing OpenSenseMapApi."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from opensensemap_api import _TITLES, OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER, SensorTypeId


@dataclass
class SensorDescr:
    """NamedTuple for describing each reported sensor."""

    id: str
    title: str
    sensor_type: SensorTypeId
    unit: str
    sensor_hw: str | None


@dataclass
class SensorVal:
    """NamedTuple for storing received sensor valus."""

    value: str
    at: datetime


class OpenSenseMapDataUpdateCoordinator(DataUpdateCoordinator):
    """My custom coordinator."""

    def __init__(
        self, hass: HomeAssistant, station_api: OpenSenseMap, config_entry: ConfigEntry
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            # Name of the data. For logging purposes.
            name=cast(str, config_entry.data.get(CONF_NAME)),
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=10),
        )
        self.station_api = station_api
        self._sensors: dict[str, SensorDescr] | None = None

    @property
    def sensors(self) -> dict[str, SensorDescr]:
        """Return the sensor description list."""
        if self._sensors is None:
            raise PlatformNotReady("Coordinator accessed before the first data fetch.")
        return self._sensors

    def init_coordinator_data(self, data: dict[str, Any]) -> None:
        """Initiate coordinator with received data."""

        # The type of a sensor needs to be derived from its title.
        # The API provides an (incomplete) mapping for different languages.
        # Store for each sensor type, which is supported by this platform, the associated
        # API titles.
        knownTitlesForSensor = {
            sId: _TITLES.get(sId.value, ()) + (sId.value,) for sId in SensorTypeId
        }

        self._sensors = {
            s["_id"]: SensorDescr(
                id=s["_id"],
                title=s["title"],
                sensor_type=foundIds[0],
                unit=s["unit"],
                sensor_hw=s.get("sensorType"),
            )
            for s in data["sensors"]
            if len(
                foundIds := [
                    sId
                    for sId in SensorTypeId
                    if s["title"] in knownTitlesForSensor[sId]
                ]
            )
            > 0
        }

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        Result is written into self.data by calling function.
        """
        try:
            await self.station_api.get_data()

        except OpenSenseMapError as err:
            LOGGER.error("Unable to fetch data: %s", err)
            raise UpdateFailed from err

        data = self.station_api.data
        if self._sensors is None:
            try:
                self.init_coordinator_data(data)
            except Exception as err:
                raise UpdateFailed from err

        return {
            s["_id"]: SensorVal(
                value=s["lastMeasurement"]["value"],
                at=datetime.fromisoformat(s["lastMeasurement"]["createdAt"]),
            )
            for s in data["sensors"]
        }
