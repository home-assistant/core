"""Support for Meteoclimatic sensor."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import MeteoclimaticUpdater
from .const import (
    ATTRIBUTION,
    CONF_STATION_CODE,
    DOMAIN,
    SENSOR_TYPE_CLASS,
    SENSOR_TYPE_ICON,
    SENSOR_TYPE_NAME,
    SENSOR_TYPE_UNIT,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteoclimatic sensor platform."""
    station_code = entry.data[CONF_STATION_CODE]
    updater = hass.data[DOMAIN][station_code]

    async_add_entities(
        [MeteoclimaticSensor(sensor_type, updater) for sensor_type in SENSOR_TYPES],
        True,
    )


class MeteoclimaticSensor(Entity):
    """Representation of a Meteoclimatic sensor."""

    def __init__(self, sensor_type: str, updater: MeteoclimaticUpdater):
        """Initialize the Meteoclimatic sensor."""
        self._type = sensor_type
        self._updater = updater
        self._state = None
        self._data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._data.station.name} {SENSOR_TYPES[self._type][SENSOR_TYPE_NAME]}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return "_".join((self._data.station.code, self._type))

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_UNIT]

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_ICON]

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_TYPES[self._type][SENSOR_TYPE_CLASS]

    def update(self):
        """Fetch new state data for the sensor."""
        self._updater.update()
        self._data = self._updater.get_data()
        self._state = getattr(self._data.weather, self._type)
