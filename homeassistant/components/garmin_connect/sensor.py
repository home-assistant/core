"""Platform for Garmin Connect integration."""
import logging
from typing import Any, Dict
from homeassistant.const import ATTR_ATTRIBUTION, CONF_ID
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import ATTRIBUTION, DOMAIN, GARMIN_ENTITY_LIST

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Garmin Connect sensor based on a config entry."""
    garmin_data = hass.data[DOMAIN][entry.entry_id]
    unique_id = entry.data[CONF_ID]
    # try:
    #     await twentemilieu.update()
    # except TwenteMilieuConnectionError as exception:
    #     raise PlatformNotReady from exception

    entities = []
    for resource in GARMIN_ENTITY_LIST:
        sensor_type = resource
        name = GARMIN_ENTITY_LIST[resource][0]
        unit = GARMIN_ENTITY_LIST[resource][1]
        icon = GARMIN_ENTITY_LIST[resource][2]

        _LOGGER.debug(
            "Registered new sensor: %s, %s, %s, %s", sensor_type, name, unit, icon
        )
        entities.append(
            GarminConnectSensor(garmin_data, unique_id, sensor_type, name, unit, icon)
        )

    async_add_entities(entities, True)


class GarminConnectSensor(Entity):
    """Representation of a Garmin Connect Sensor."""

    def __init__(self, data, unique_id, sensor_type, name, unit, icon):
        """Initialize the sensor."""
        self._data = data
        self._unique_id = unique_id
        self._available = True
        self._type = sensor_type
        self._name = name
        self._icon = icon
        self._unit = unit
        self._unsub_dispatcher = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{DOMAIN}_{self._unique_id}_{self._type}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return attributes for sensor."""

        attributes = {}
        if self._data.data:
            attributes = {
                "source": self._data.data["source"],
                "last_synced": self._data.data["lastSyncTimestampGMT"],
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }
        return attributes

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information about Twente Milieu."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
            "name": "Garmin Connect",
            "manufacturer": "Garmin Connect",
            "model": "Fitness Tracker",
        }

    async def async_added_to_hass(self):
        """Register state update callback."""
        pass

    async def async_will_remove_from_hass(self):
        """Prepare for unload."""
        pass

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_update(self):
        """Get the latest data and use it to update our sensor state."""

        await self._data.async_update()
        if not self._data.data:
            _LOGGER.error("Didn't receive data from TOON")
            return

        data = self._data.data
        if "Duration" in self._type:
            self._state = data[self._type] // 60
        elif "Seconds" in self._type:
            self._state = data[self._type] // 60
        else:
            self._state = data[self._type]

        _LOGGER.debug(
            "Device %s set to state %s %s", self._type, self._state, self._unit
        )
