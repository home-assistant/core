"""Support for Meteoclimatic sensor."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTRIBUTION,
    DOMAIN,
    METEOCLIMATIC_COORDINATOR,
    METEOCLIMATIC_STATION_CODE,
    METEOCLIMATIC_STATION_NAME,
    METEOCLIMATIC_UPDATER,
    SENSOR_TYPE_CLASS,
    SENSOR_TYPE_ICON,
    SENSOR_TYPE_NAME,
    SENSOR_TYPE_UNIT,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_STATION_CODE = "station_code"
ATTR_STATION_NAME = "station_name"


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteoclimatic sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [MeteoclimaticSensor(sensor_type, hass_data) for sensor_type in SENSOR_TYPES],
        False,
    )


class MeteoclimaticSensor(Entity):
    """Representation of a Meteoclimatic sensor."""

    def __init__(self, sensor_type: str, hass_data: dict):
        """Initialize the Meteoclimatic sensor."""
        self._type = sensor_type
        self._unique_id = f"{hass_data[METEOCLIMATIC_STATION_CODE]}_{self._type}"
        self._name = f"{hass_data[METEOCLIMATIC_STATION_NAME]} {SENSOR_TYPES[self._type][SENSOR_TYPE_NAME]}"
        self._updater = hass_data[METEOCLIMATIC_UPDATER]
        self._coordinator = hass_data[METEOCLIMATIC_COORDINATOR]

        self._data = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return (
            getattr(self._data.weather, self._type)
            if self._data is not None and hasattr(self._data, "weather")
            else None
        )

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

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: self._data.reception_time if self._data else None,
            ATTR_SENSOR_ID: self._type,
            ATTR_STATION_CODE: self._data.station.code if self._data else None,
            ATTR_STATION_NAME: self._data.station.name if self._data else None,
        }

    async def async_added_to_hass(self) -> None:
        """Set up a listener and load data."""
        self.async_on_remove(
            self._coordinator.async_add_listener(self._update_callback)
        )
        self._update_callback()

    async def async_update(self):
        """Schedule a custom update via the common entity update service."""
        await self._coordinator.async_request_refresh()

    @callback
    def _update_callback(self) -> None:
        """Load data from integration."""
        self._data = self._updater.get_data()
        self.async_write_ha_state()

    @property
    def should_poll(self) -> bool:
        """Entities do not individually poll."""
        return False

    @property
    def available(self):
        """Return if state is available."""
        return self._coordinator.last_update_success
