"""Opensprinkler integration."""
from datetime import datetime
import logging
from typing import Callable

import pytz

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import OpensprinklerSensor
from .const import DATA_DEVICES, DOMAIN

_LOGGER = logging.getLogger(__name__)
UTC_TZ = pytz.timezone("UTC")


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: Callable,
    discovery_info: dict,
):
    """Set up the opensprinkler sensors."""
    entities = await hass.async_add_executor_job(
        _create_entities, hass, config, discovery_info
    )
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, config: dict, discovery_info: dict):
    entities = []

    name = discovery_info["name"]
    device = hass.data[DOMAIN][DATA_DEVICES][name]

    entities.append(LastRunSensor(name, device))
    entities.append(RainDelayStopTimeSensor(name, device))
    entities.append(WaterLevelSensor(name, device))

    for station in device.stations:
        entities.append(StationSensor(station, device))

    return entities


class WaterLevelSensor(OpensprinklerSensor, Entity):
    """Represent a sensor that for water level."""

    def __init__(self, name, device):
        """Set up a new opensprinkler water level sensor."""
        self._name = name
        self._device = device
        super().__init__()

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:water"

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return f"{self._name} Water Level"

    @property
    def unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return "%"

    def _get_state(self) -> int:
        """Retrieve latest state."""
        return self._device.device.water_level


class LastRunSensor(OpensprinklerSensor, Entity):
    """Represent a sensor that for last run time."""

    def __init__(self, name, device):
        """Set up a new opensprinkler last run sensor."""
        self._name = name
        self._device = device
        super().__init__()

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:history"

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return f"{self._name} Last Run"

    def _get_state(self):
        """Retrieve latest state."""
        last_run = self._device.device.last_run
        utc_time = datetime.fromtimestamp(last_run, UTC_TZ)
        return utc_time.strftime("%d/%m %H:%M")


class RainDelayStopTimeSensor(OpensprinklerSensor, Entity):
    """Represent a sensor that for rain delay stop time."""

    def __init__(self, name, device):
        """Set up a new opensprinkler rain delay stop time sensor."""
        self._name = name
        self._device = device
        super().__init__()

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:weather-rainy"

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return f"{self._name} Rain Delay Stop Time"

    def _get_state(self):
        """Retrieve latest state."""
        rdst = self._device.device.rain_delay_stop_time
        if rdst == 0:
            return "Not in effect"

        utc_time = datetime.fromtimestamp(rdst, UTC_TZ)
        return utc_time.strftime("%d/%m %H:%M")


class StationSensor(OpensprinklerSensor, Entity):
    """Represent a sensor for status of station."""

    def __init__(self, station, device):
        """Set up a new opensprinkler device sensor."""
        self._station = station
        self._device = device
        super().__init__()

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._station.name

    def _get_state(self) -> bool:
        """Retrieve latest state."""
        return self._station.status
