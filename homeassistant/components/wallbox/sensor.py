"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""

from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    CONF_CONNECTIONS,
    DOMAIN,
    CONF_SENSOR_TYPES,
    CONF_ROUND,
    CONF_ICON,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
)

CONF_STATION = "station"
UPDATE_INTERVAL = 30


_LOGGER = logging.getLogger(__name__)


async def wallbox_updater(wallbox, hass):
    """Get new sensor data for Wallbox component."""
    data = await wallbox.async_get_data(hass)

    filtered_data = {k: data[k] for k in CONF_SENSOR_TYPES if k in data}

    for key, value in filtered_data.items():
        sensor_round = CONF_SENSOR_TYPES[key][CONF_ROUND]
        if sensor_round:
            try:
                filtered_data[key] = round(value, sensor_round)
            except TypeError:
                _LOGGER.debug("Cannot format %s", key)

    return filtered_data


async def async_setup_entry(hass, config, async_add_entities):
    """Create wallbox sensor entities in HASS."""
    wallbox = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]

    async def async_update_data():
        return await wallbox_updater(wallbox, hass)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="wallbox",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        WallboxSensor(coordinator, idx, ent, config)
        for idx, ent in enumerate(coordinator.data)
    )


class WallboxSensor(CoordinatorEntity, Entity):
    """Representation of the Wallbox portal."""

    def __init__(self, coordinator, idx, ent, config):
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        self._properties = CONF_SENSOR_TYPES[ent]
        self._name = f"{config.title} {self._properties[CONF_NAME]}"
        self._icon = self._properties[CONF_ICON]
        self._unit = self._properties[CONF_UNIT_OF_MEASUREMENT]
        self._ent = ent

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._ent]

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon
