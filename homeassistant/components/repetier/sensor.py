"""Support for monitoring Repetier Server Sensors."""
from datetime import datetime
import logging
import time

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import REPETIER_API, SENSOR_TYPES, UPDATE_SIGNAL

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Repetier Server sensors."""
    if discovery_info is None:
        return

    sensor_map = {
        "bed_temperature": RepetierTempSensor,
        "extruder_temperature": RepetierTempSensor,
        "chamber_temperature": RepetierTempSensor,
        "current_state": RepetierSensor,
        "current_job": RepetierJobSensor,
        "job_end": RepetierJobEndSensor,
        "job_start": RepetierJobStartSensor,
    }

    entities = []
    for info in discovery_info:
        printer_name = info["printer_name"]
        api = hass.data[REPETIER_API][printer_name]
        printer_id = info["printer_id"]
        sensor_type = info["sensor_type"]
        temp_id = info["temp_id"]
        name = f"{info['name']}{SENSOR_TYPES[sensor_type][3]}"
        if temp_id is not None:
            _LOGGER.debug("%s Temp_id: %s", sensor_type, temp_id)
            name = f"{name}{temp_id}"
        sensor_class = sensor_map[sensor_type]
        entity = sensor_class(api, temp_id, name, printer_id, sensor_type)
        entities.append(entity)

    add_entities(entities, True)


class RepetierSensor(SensorEntity):
    """Class to create and populate a Repetier Sensor."""

    def __init__(self, api, temp_id, name, printer_id, sensor_type):
        """Init new sensor."""
        self._api = api
        self._attributes = {}
        self._available = False
        self._temp_id = temp_id
        self._name = name
        self._printer_id = printer_id
        self._sensor_type = sensor_type
        self._state = None
        self._attr_device_class = SENSOR_TYPES[self._sensor_type][4]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def extra_state_attributes(self):
        """Return sensor attributes."""
        return self._attributes

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return SENSOR_TYPES[self._sensor_type][2]

    @property
    def should_poll(self):
        """Return False as entity is updated from the component."""
        return False

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @callback
    def update_callback(self):
        """Get new data and update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Connect update callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, UPDATE_SIGNAL, self.update_callback)
        )

    def _get_data(self):
        """Return new data from the api cache."""
        data = self._api.get_data(self._printer_id, self._sensor_type, self._temp_id)
        if data is None:
            _LOGGER.debug(
                "Data not found for %s and %s", self._sensor_type, self._temp_id
            )
            self._available = False
            return None
        self._available = True
        return data

    def update(self):
        """Update the sensor."""
        data = self._get_data()
        if data is None:
            return
        state = data.pop("state")
        _LOGGER.debug("Printer %s State %s", self._name, state)
        self._attributes.update(data)
        self._state = state


class RepetierTempSensor(RepetierSensor):
    """Represent a Repetier temp sensor."""

    @property
    def state(self):
        """Return sensor state."""
        if self._state is None:
            return None
        return round(self._state, 2)

    def update(self):
        """Update the sensor."""
        data = self._get_data()
        if data is None:
            return
        state = data.pop("state")
        temp_set = data["temp_set"]
        _LOGGER.debug("Printer %s Setpoint: %s, Temp: %s", self._name, temp_set, state)
        self._attributes.update(data)
        self._state = state


class RepetierJobSensor(RepetierSensor):
    """Represent a Repetier job sensor."""

    @property
    def state(self):
        """Return sensor state."""
        if self._state is None:
            return None
        return round(self._state, 2)


class RepetierJobEndSensor(RepetierSensor):
    """Class to create and populate a Repetier Job End timestamp Sensor."""

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    def update(self):
        """Update the sensor."""
        data = self._get_data()
        if data is None:
            return
        job_name = data["job_name"]
        start = data["start"]
        print_time = data["print_time"]
        from_start = data["from_start"]
        time_end = start + round(print_time, 0)
        self._state = datetime.utcfromtimestamp(time_end).isoformat()
        remaining = print_time - from_start
        remaining_secs = int(round(remaining, 0))
        _LOGGER.debug(
            "Job %s remaining %s",
            job_name,
            time.strftime("%H:%M:%S", time.gmtime(remaining_secs)),
        )


class RepetierJobStartSensor(RepetierSensor):
    """Class to create and populate a Repetier Job Start timestamp Sensor."""

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    def update(self):
        """Update the sensor."""
        data = self._get_data()
        if data is None:
            return
        job_name = data["job_name"]
        start = data["start"]
        from_start = data["from_start"]
        self._state = datetime.utcfromtimestamp(start).isoformat()
        elapsed_secs = int(round(from_start, 0))
        _LOGGER.debug(
            "Job %s elapsed %s",
            job_name,
            time.strftime("%H:%M:%S", time.gmtime(elapsed_secs)),
        )
