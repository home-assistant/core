"""Support for Ebusd sensors."""
from __future__ import annotations

import datetime
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from .const import CONF_CIRCUIT, DOMAIN, SENSOR_TYPES

TIME_FRAME1_BEGIN = "time_frame1_begin"
TIME_FRAME1_END = "time_frame1_end"
TIME_FRAME2_BEGIN = "time_frame2_begin"
TIME_FRAME2_END = "time_frame2_end"
TIME_FRAME3_BEGIN = "time_frame3_begin"
TIME_FRAME3_END = "time_frame3_end"
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ebus sensor."""
    ebusd_api = hass.data[DOMAIN][entry.entry_id]
    monitored_conditions = entry.data[CONF_MONITORED_CONDITIONS]
    name = entry.data[CONF_NAME]
    sensor_types = SENSOR_TYPES[entry.data[CONF_CIRCUIT]]

    sensors = []
    for condition in monitored_conditions:
        sensors.append(EbusdSensor(ebusd_api, sensor_types[condition], name))

    async_add_entities(sensors, True)


class EbusdSensor(SensorEntity):
    """Ebusd component sensor methods definition."""

    def __init__(self, data, sensor, name):
        """Initialize the sensor."""
        self._state = None
        self._client_name = name
        (
            self._name,
            self._unit_of_measurement,
            self._icon,
            self._type,
            self._device_class,
        ) = sensor
        self.data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._client_name} {self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self._type == 1 and self._state is not None:
            schedule = {
                TIME_FRAME1_BEGIN: None,
                TIME_FRAME1_END: None,
                TIME_FRAME2_BEGIN: None,
                TIME_FRAME2_END: None,
                TIME_FRAME3_BEGIN: None,
                TIME_FRAME3_END: None,
            }
            time_frame = self._state.split(";")
            for index, item in enumerate(sorted(schedule.items())):
                if index < len(time_frame):
                    parsed = datetime.datetime.strptime(time_frame[index], "%H:%M")
                    parsed = parsed.replace(
                        dt_util.now().year, dt_util.now().month, dt_util.now().day
                    )
                    schedule[item[0]] = parsed.isoformat()
            return schedule
        return None

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self.data.update(self._name, self._type)
            if self._name not in self.data.value:
                return

            self._state = self.data.value[self._name]
        except RuntimeError:
            _LOGGER.debug("EbusdData.update exception")
