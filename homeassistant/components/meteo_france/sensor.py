"""Support for Meteo-France raining forecast sensor."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from . import MeteoFranceDataUpdateCoordinator
from .const import (
    ATTRIBUTION,
    DOMAIN,
    ENTITY_API_DATA_PATH,
    ENTITY_CLASS,
    ENTITY_ENABLE,
    ENTITY_ICON,
    ENTITY_NAME,
    ENTITY_UNIT,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Meteo-France sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [MeteoFranceSensor(sensor_type, coordinator) for sensor_type in SENSOR_TYPES],
        True,
    )


class MeteoFranceSensor(Entity):
    """Representation of a Meteo-France sensor."""

    def __init__(self, sensor_type: str, coordinator: MeteoFranceDataUpdateCoordinator):
        """Initialize the Meteo-France sensor."""
        self._type = sensor_type
        self.coordinator = coordinator
        city_name = self.coordinator.data.position["name"]
        self._name = f"{city_name} {SENSOR_TYPES[self._type][ENTITY_NAME]}"

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._name

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        path = SENSOR_TYPES[self._type][ENTITY_API_DATA_PATH].split(":")
        data = getattr(self.coordinator.data, path[0])
        if path[0] == "forecast":
            data = data[2]
        else:
            data = data[0]
        # _LOGGER.info("-"*80)
        # _LOGGER.warning(self._type)
        # _LOGGER.error(path)
        # _LOGGER.error(data)

        # # if len(path) == 3:
        # #     _LOGGER.warning(data[path[1]][path[2]])
        # #     _LOGGER.warning("OK-2")
        # # _LOGGER.warning(data[path[1]])
        # # _LOGGER.warning("OK")

        # _LOGGER.info("-"*80)
        if len(path) == 3:
            return data[path[1]][path[2]]
        return data[path[1]]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        # Attributes for next_rain sensor.
        if self._type == "next_rain":
            return {
                # **{STATE_ATTR_FORECAST: self._data["rain_forecast"]},
                # **self._data["next_rain_intervals"],
                **{ATTR_ATTRIBUTION: ATTRIBUTION},
            }

        # Attributes for weather_alert sensor.
        if self._type == "weather_alert":
            return {
                # **{STATE_ATTR_BULLETIN_TIME: self._alert_watcher.bulletin_date},
                # **self._alert_watcher.alerts_list,
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }

        # Attributes for all other sensors.
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._type][ENTITY_UNIT]

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self._type][ENTITY_ICON]

    @property
    def device_class(self):
        """Return the device class."""
        return SENSOR_TYPES[self._type][ENTITY_CLASS]

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return SENSOR_TYPES[self._type][ENTITY_ENABLE]

    @property
    def available(self):
        """Return if state is available."""
        return self.coordinator.last_update_success

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_update(self):
        """Only used by the generic entity update service."""
        if not self.enabled:
            return

        await self.coordinator.async_request_refresh()
