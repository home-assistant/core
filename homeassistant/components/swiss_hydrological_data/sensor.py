"""Support for hydrological data from the Fed. Office for the Environment."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from swisshydrodata import SwissHydroData
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTR_MAX_24H = "max-24h"
ATTR_MEAN_24H = "mean-24h"
ATTR_MIN_24H = "min-24h"
ATTR_STATION = "station"
ATTR_STATION_UPDATE = "station_update"
ATTR_WATER_BODY = "water_body"
ATTR_WATER_BODY_TYPE = "water_body_type"

CONF_STATION = "station"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_DISCHARGE = "discharge"
SENSOR_LEVEL = "level"
SENSOR_TEMPERATURE = "temperature"

CONDITIONS = {
    SENSOR_DISCHARGE: "mdi:waves",
    SENSOR_LEVEL: "mdi:zodiac-aquarius",
    SENSOR_TEMPERATURE: "mdi:oil-temperature",
}

CONDITION_DETAILS = [
    ATTR_MAX_24H,
    ATTR_MEAN_24H,
    ATTR_MIN_24H,
]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_STATION): vol.Coerce(int),
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[SENSOR_TEMPERATURE]): vol.All(
            cv.ensure_list, [vol.In(CONDITIONS)]
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Swiss hydrological sensor."""
    station: int = config[CONF_STATION]
    monitored_conditions: list[str] = config[CONF_MONITORED_CONDITIONS]

    hydro_data = HydrologicalData(station)
    hydro_data.update()

    if hydro_data.data is None:
        _LOGGER.error("The station doesn't exists: %s", station)
        return

    add_entities(
        (
            SwissHydrologicalDataSensor(hydro_data, station, condition)
            for condition in monitored_conditions
        ),
        True,
    )


class SwissHydrologicalDataSensor(SensorEntity):
    """Implementation of a Swiss hydrological sensor."""

    _attr_attribution = (
        "Data provided by the Swiss Federal Office for the Environment FOEN"
    )

    def __init__(
        self, hydro_data: HydrologicalData, station: int, condition: str
    ) -> None:
        """Initialize the Swiss hydrological sensor."""
        self.hydro_data = hydro_data
        data = hydro_data.data
        if TYPE_CHECKING:
            # Setup will fail in setup_platform if the data is None.
            assert data is not None

        self._condition = condition
        self._data: dict[str, Any] | None = data
        self._attr_icon = CONDITIONS[condition]
        self._attr_name = f"{data['water-body-name']} {condition}"
        self._attr_native_unit_of_measurement = data["parameters"][condition]["unit"]
        self._attr_unique_id = f"{station}_{condition}"
        self._station = station

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attrs: dict[str, Any] = {}

        if not self._data:
            return attrs

        attrs[ATTR_WATER_BODY_TYPE] = self._data["water-body-type"]
        attrs[ATTR_STATION] = self._data["name"]
        attrs[ATTR_STATION_UPDATE] = self._data["parameters"][self._condition][
            "datetime"
        ]

        for entry in CONDITION_DETAILS:
            attrs[entry.replace("-", "_")] = self._data["parameters"][self._condition][
                entry
            ]

        return attrs

    def update(self) -> None:
        """Get the latest data and update the state."""
        self.hydro_data.update()
        self._data = self.hydro_data.data

        self._attr_native_value = None
        if self._data is not None:
            state = self._data["parameters"][self._condition]["value"]
            if isinstance(state, (int, float)):
                self._attr_native_value = round(state, 2)


class HydrologicalData:
    """The Class for handling the data retrieval."""

    def __init__(self, station: int) -> None:
        """Initialize the data object."""
        self.station = station
        self.data: dict[str, Any] | None = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data."""

        shd = SwissHydroData()
        self.data = shd.get_station(self.station)
