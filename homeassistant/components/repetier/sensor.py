"""Support for monitoring Repetier Server Sensors."""
from datetime import datetime
import logging
import time

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import REPETIER_API, SENSOR_TYPES, UPDATE_SIGNAL

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Repetier Server sensors."""
    if discovery_info is None:
        return

    sensor_map = {
        'bed_temperature': RepetierBedSensor,
        'extruder_temperature': RepetierExtruderSensor,
        'chamber_temperature': RepetierChamberSensor,
        'current_state': RepetierStateSensor,
        'current_job': RepetierJobSensor,
        'time_remaining': RepetierRemainingSensor,
        'time_elapsed': RepetierElapsedSensor,
    }

    entities = []
    for info in discovery_info:
        printer_name = info['printer_name']
        api = hass.data[REPETIER_API][printer_name]
        printer_id = info['printer_id']
        sensor_type = info['sensor_type']
        data_key = info['data_key']
        name = info['name']
        if data_key is not None:
            name = '{}{}{}'.format(
                name, SENSOR_TYPES[sensor_type][3], data_key)
        else:
            name = '{}{}'.format(name, SENSOR_TYPES[sensor_type][3])
        sensor_class = sensor_map[sensor_type]
        entity = sensor_class(api, data_key, name, printer_id, sensor_type)
        entities.append(entity)

    add_entities(entities, True)


class RepetierSensor(Entity):
    """Class to create and populate a Repetier Sensor."""

    def __init__(self, api, data_key, name, printer_id, sensor_type):
        """Init new sensor."""
        self._api = api
        self._attributes = {}
        self._available = False
        self._data_key = data_key
        self._name = name
        self._printer_id = printer_id
        self._sensor_type = sensor_type
        self._state = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
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

    @callback
    def update_callback(self):
        """Get new data and update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Connect update callbacks."""
        async_dispatcher_connect(
            self.hass, UPDATE_SIGNAL, self.update_callback)

    def _get_data(self):
        """Return new data from the api cache."""
        data = self._api.get_data(self._sensor_type, self._data_key)
        if data is None:
            _LOGGER.debug(
                "Data not found for %s and %s",
                self._sensor_type, self._data_key)
            self._available = False
            return None
        self._available = True
        return data


class RepetierBedSensor(RepetierSensor):
    """Class to create and populate a Repetier Bed Sensor."""

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
        temp = data.pop('temp')
        temp_set = data['temp_set']
        _LOGGER.debug(
            "Bed %s Setpoint: %s, Temp: %s", self._data_key, temp_set, temp)
        self._attributes.update(data)
        self._state = temp


class RepetierExtruderSensor(RepetierSensor):
    """Class to create and populate a Repetier Nozzle Sensor."""

    @property
    def state(self):
        """Return sensor state."""
        if self._state is None:
            return None
        return round(self._state, 2)

    def update(self):
        """Update the sensor."""
        self._printer.get_data()
        if self._printer.extruder is None:
            self._available = False
            return
        if self._printer.state == "off":
            self._available = False
            return
        self._available = True
        temp_set = self._printer.extruder[self._data_key].tempset
        temp = self._printer.extruder[self._data_key].tempread
        output = self._printer.extruder[self._data_key].output
        _LOGGER.debug("Extruder %s Setpoint: %s, Temp: %s",
                      self._data_key,
                      temp_set,
                      temp)
        self._attributes['setpoint'] = temp_set
        self._attributes['output'] = output
        self._state = temp


class RepetierChamberSensor(RepetierSensor):
    """Class to create and populate a Repetier Nozzle Sensor."""

    @property
    def state(self):
        """Return sensor state."""
        if self._state is None:
            return None
        return round(self._state, 2)

    def update(self):
        """Update the sensor."""
        self._printer.get_data()
        if self._printer.heatedchambers is None:
            self._available = False
            return
        if self._printer.state == "off":
            self._available = False
            return
        self._available = True
        temp_set = self._printer.chamber[self._data_key].tempset
        temp = self._printer.chamber[self._data_key].tempread
        output = self._printer.chamber[self._data_key].output
        _LOGGER.debug("Chamber %s Setpoint: %s, Temp: %s",
                      self._data_key,
                      temp_set,
                      temp)
        self._attributes['setpoint'] = temp_set
        self._attributes['output'] = output
        self._state = temp


class RepetierStateSensor(RepetierSensor):
    """Class to create and populate a Repetier State Sensor."""

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    def update(self):
        """Update the sensor."""
        self._printer.get_data()
        if self._printer.state is None:
            self._available = False
            return
        self._available = True
        state = self._printer.state
        _LOGGER.debug("Printer %s State %s",
                      self._printer.name,
                      state)
        self._attributes['active_extruder'] = self._printer.activeextruder
        self._attributes['x_homed'] = self._printer.hasxhome
        self._attributes['y_homed'] = self._printer.hasyhome
        self._attributes['z_homed'] = self._printer.haszhome
        self._attributes['firmware'] = self._printer.firmware
        self._attributes['firmware_url'] = self._printer.firmwareurl
        self._state = state


class RepetierJobSensor(RepetierSensor):
    """Class to create and populate a Repetier Job Sensor."""

    @property
    def state(self):
        """Return sensor state."""
        if self._state is None:
            return None
        return round(self._state, 2)

    def update(self):
        """Update the sensor."""
        self._printer.get_data()
        if self._printer.job is None:
            self._available = False
            return
        if self._printer.state == "off":
            self._available = False
            return
        self._available = True
        pct_done = self._printer.done
        job_name = self._printer.job
        _LOGGER.debug("Job %s State %s",
                      job_name,
                      pct_done)
        self._attributes['job_name'] = job_name
        self._attributes['job_id'] = self._printer.jobid
        self._attributes['total_lines'] = self._printer.totallines
        self._attributes['lines_sent'] = self._printer.linessent
        self._attributes['total_layers'] = self._printer.oflayer
        self._attributes['current_layer'] = self._printer.layer
        self._attributes['feed_rate'] = self._printer.speedmultiply
        self._attributes['flow'] = self._printer.flowmultiply
        self._attributes['x'] = self._printer.x
        self._attributes['y'] = self._printer.y
        self._attributes['z'] = self._printer.z
        self._state = pct_done


class RepetierRemainingSensor(RepetierSensor):
    """Class to create and populate a Repetier Time Remaining Sensor."""

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    def update(self):
        """Update the sensor."""
        self._printer.get_data()
        if self._printer.job is None:
            self._available = False
            return
        if self._printer.state == "off":
            self._available = False
            return
        start = self._printer.start
        end = self._printer.printtime
        if start is None or end is None:
            self._available = False
            return
        self._available = True
        from_start = self._printer.printedtimecomp
        remaining = end - from_start
        tend = start + round(end, 0)
        dtime = datetime.utcfromtimestamp(tend).isoformat()
        endtime = dtime
        secs = int(round(remaining, 0))
        state = time.strftime('%H:%M:%S', time.gmtime(secs))

        _LOGGER.debug("Job %s remaining %s",
                      self._printer.job,
                      state)
        self._attributes['finished'] = endtime
        self._attributes['seconds'] = secs
        self._state = state


class RepetierElapsedSensor(RepetierSensor):
    """Class to create and populate a Repetier Time Elapsed Sensor."""

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    def update(self):
        """Update the sensor."""
        self._printer.get_data()
        if self._printer.job is None:
            self._available = False
            return
        if self._printer.state == "off":
            self._available = False
            return
        start = self._printer.start
        printtime = self._printer.printedtimecomp
        if start is None or printtime is None:
            self._available = False
            return
        self._available = True
        dtime = datetime.utcfromtimestamp(start).isoformat()
        starttime = dtime
        secs = int(round(printtime, 0))
        state = time.strftime('%H:%M:%S', time.gmtime(secs))

        _LOGGER.debug("Job %s elapsed %s",
                      self._printer.job,
                      state)
        self._attributes['started'] = starttime
        self._attributes['seconds'] = secs
        self._state = state
