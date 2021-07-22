"""Support for Luftdaten sensors."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_SHOW_ON_MAP,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import (
    DATA_LUFTDATEN,
    DATA_LUFTDATEN_CLIENT,
    DEFAULT_ATTRIBUTION,
    DOMAIN,
    SENSORS,
    TOPIC_UPDATE,
)
from .const import ATTR_SENSOR_ID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up a Luftdaten sensor based on a config entry."""
    luftdaten = hass.data[DOMAIN][DATA_LUFTDATEN_CLIENT][entry.entry_id]

    sensors = []
    for sensor_type in luftdaten.sensor_conditions:
        try:
            name, icon, unit, device_class = SENSORS[sensor_type]
        except KeyError:
            _LOGGER.debug("Unknown sensor value type: %s", sensor_type)
            continue

        sensors.append(
            LuftdatenSensor(
                luftdaten,
                sensor_type,
                name,
                icon,
                unit,
                device_class,
                entry.data[CONF_SHOW_ON_MAP],
            )
        )

    async_add_entities(sensors, True)


class LuftdatenSensor(SensorEntity):
    """Implementation of a Luftdaten sensor."""

    def __init__(self, luftdaten, sensor_type, name, icon, unit, device_class, show):
        """Initialize the Luftdaten sensor."""
        self._async_unsub_dispatcher_connect = None
        self.luftdaten = luftdaten
        self._icon = icon
        self._name = name
        self._data = None
        self.sensor_type = sensor_type
        self._unit_of_measurement = unit
        self._show_on_map = show
        self._attrs = {}
        self._attr_device_class = device_class

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def state(self):
        """Return the state of the device."""
        if self._data is not None:
            try:
                return self._data[self.sensor_type]
            except KeyError:
                return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique, friendly identifier for this entity."""
        if self._data is not None:
            try:
                return f"{self._data['sensor_id']}_{self.sensor_type}"
            except KeyError:
                return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        self._attrs[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION

        if self._data is not None:
            try:
                self._attrs[ATTR_SENSOR_ID] = self._data["sensor_id"]
            except KeyError:
                return None

            on_map = ATTR_LATITUDE, ATTR_LONGITUDE
            no_map = "lat", "long"
            lat_format, lon_format = on_map if self._show_on_map else no_map
            try:
                self._attrs[lon_format] = self._data["longitude"]
                self._attrs[lat_format] = self._data["latitude"]
                return self._attrs
            except KeyError:
                return

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            self._data = self.luftdaten.data[DATA_LUFTDATEN]
        except KeyError:
            return
