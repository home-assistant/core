"""Opensprinkler integration."""
import logging
from typing import Callable

from homeassistant.const import CONF_NAME, DEVICE_CLASS_TIMESTAMP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utc_from_timestamp

from . import OpensprinklerCoordinator, OpensprinklerSensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: dict, async_add_entities: Callable,
):
    """Set up the opensprinkler sensors."""
    entities = _create_entities(hass, entry)
    async_add_entities(entities)


def _create_entities(hass: HomeAssistant, entry: dict):
    entities = []

    device = hass.data[DOMAIN][entry.entry_id]
    name = entry.data[CONF_NAME]
    coordinator = OpensprinklerCoordinator(hass, device)

    entities.append(LastRunSensor(entry.entry_id, name, device, coordinator))
    entities.append(RainDelayStopTimeSensor(entry.entry_id, name, device, coordinator))
    entities.append(WaterLevelSensor(entry.entry_id, name, device, coordinator))

    for station in device.stations:
        entities.append(StationSensor(entry.entry_id, station, device, coordinator))

    return entities


class WaterLevelSensor(OpensprinklerSensor, Entity):
    """Represent a sensor that for water level."""

    def __init__(self, entry_id, name, device, coordinator):
        """Set up a new opensprinkler water level sensor."""
        self._entry_id = entry_id
        self._name = name
        self._device = device
        self._entity_type = "sensor"
        super().__init__(coordinator)

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:water"

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return f"{self._name} Water Level"

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_water_level"

    @property
    def unit_of_measurement(self) -> str:
        """Return the units of measurement."""
        return "%"

    def _get_state(self) -> int:
        """Retrieve latest state."""
        return self._device.device.water_level


class LastRunSensor(OpensprinklerSensor, Entity):
    """Represent a sensor that for last run time."""

    def __init__(self, entry_id, name, device, coordinator):
        """Set up a new opensprinkler last run sensor."""
        self._entry_id = entry_id
        self._name = name
        self._device = device
        self._entity_type = "sensor"
        super().__init__(coordinator)

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:history"

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return f"{self._name} Last Run"

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_last_run"

    def _get_state(self):
        """Retrieve latest state."""
        last_run = self._device.device.last_run
        return utc_from_timestamp(last_run).isoformat()


class RainDelayStopTimeSensor(OpensprinklerSensor, Entity):
    """Represent a sensor that for rain delay stop time."""

    def __init__(self, entry_id, name, device, coordinator):
        """Set up a new opensprinkler rain delay stop time sensor."""
        self._entry_id = entry_id
        self._name = name
        self._device = device
        self._entity_type = "sensor"
        super().__init__(coordinator)

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:weather-rainy"

    @property
    def name(self) -> str:
        """Return the name of this sensor including the device name."""
        return f"{self._name} Rain Delay Stop Time"

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_rdst"

    def _get_state(self):
        """Retrieve latest state."""
        rdst = self._device.device.rain_delay_stop_time
        if rdst == 0:
            return None

        return utc_from_timestamp(rdst).isoformat()


class StationSensor(OpensprinklerSensor, Entity):
    """Represent a sensor for status of station."""

    def __init__(self, entry_id, station, device, coordinator):
        """Set up a new opensprinkler device sensor."""
        self._entry_id = entry_id
        self._station = station
        self._device = device
        self._entity_type = "sensor"
        super().__init__(coordinator)

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._station.name

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._entry_id}_{self._entity_type}_station_{self._station.index}"

    def _get_state(self) -> str:
        """Retrieve latest state."""
        return self._station.status
