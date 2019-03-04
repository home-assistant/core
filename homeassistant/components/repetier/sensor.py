"""Support for monitoring Repetier Server Sensors"""
import logging
from datetime import timedelta, datetime

from homeassistant.components.repetier import (SENSOR_TYPES,
                                               DOMAIN as COMPONENT_DOMAIN)
from homeassistant.const import (TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['repetier']

SCAN_INTERVAL = timedelta(seconds=5)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available Repetier Server sensors."""
    import pyrepetier
    if discovery_info is None:
        return

    id = discovery_info['printer']
    url = discovery_info['url']
    port = discovery_info['port']
    apikey = discovery_info['apikey']
    monitored_conditions = discovery_info['sensors']

    def refresh(event_time):
        """Update sensors"""
        _addDevice()

    track_time_interval(hass, refresh, SCAN_INTERVAL)

    def _addDevice():
        """Add devices"""
        server = pyrepetier.Repetier(
            url=url,
            port=port,
            apikey=apikey)
        printers = server.getPrinters()

        devices = []

        for sens_type in monitored_conditions:
            _LOGGER.debug("Checking for %s sensor types on %s", sens_type, printers[id]['name'])
            if sens_type == 'Temperatures':
                nozzles = server.Nozzle(id)
                if nozzles != None:
                    for nozzle in nozzles:
                        state = hass.states.get('sensor.' + printers[id]['slug'] + '_nozzle_' + str(nozzle))
                        if not state:
                            new_sensor = RepetierSensor('nozzle', {'nozzle': nozzle,
                                                                   'name': printers[id]['slug'],
                                                                   'id': id,
                                                                   'server': {'url': url, 'port': port, 'apikey': apikey},
                                                                   'sens_type': sens_type})
                            devices.append(new_sensor)
                else:
                    _LOGGER.debug("No nozzles found - is printer %s offline?", printers[id]['name'])

                beds = server.Bed(id)
                if beds != None:
                    for bed in beds:
                        state = hass.states.get('sensor.' + printers[id]['slug'] + '_bed_' + str(bed))
                        if not state:
                            new_sensor = RepetierSensor('bed', {'bed': bed,
                                                                'name': printers[id]['slug'],
                                                                'id': id,
                                                                'server': {'url': url, 'port': port, 'apikey': apikey},
                                                                'sens_type': sens_type})
                            devices.append(new_sensor)
                else:
                    _LOGGER.debug("No beds found - is printer %s offline?", printers[id]['name'])

            elif sens_type == "Current State":
                state = hass.states.get('sensor.' + printers[id]['slug'])
                if not state:
                    _LOGGER.debug("State sensor initiating...")
                    new_sensor = RepetierSensor('state', {'name': printers[id]['slug'],
                                                          'id': id,
                                                          'server': {'url': url, 'port': port, 'apikey': apikey},
                                                          'sens_type': sens_type})
                    devices.append(new_sensor)
            elif sens_type == "Job Percentage":
                state = hass.states.get('sensor.' + printers[id]['slug'] + '_current_job')
                if not state:
                    _LOGGER.debug("Job percentage sensor initiating...")
                    new_sensor = RepetierSensor('percentage', {'name': printers[id]['slug'],
                                                               'id': id,
                                                               'server': {'url': url, 'port': port, 'apikey': apikey},
                                                               'sens_type': sens_type})
                    devices.append(new_sensor)
            elif sens_type == "Time Remaining":
                state = hass.states.get('sensor.' + printers[id]['slug'] + '_current_job_remaining')
                if not state:
                    _LOGGER.debug("Time remaining sensor initiating...")
                    new_sensor = RepetierSensor('remaining', {'name': printers[id]['slug'],
                                                              'id': id,
                                                              'server': {'url': url, 'port': port, 'apikey': apikey},
                                                              'sens_type': sens_type})
                    devices.append(new_sensor)
            elif sens_type == "Time Elapsed":
                state = hass.states.get('sensor.' + printers[id]['slug'] + '_current_job_elapsed')
                if not state:
                    _LOGGER.debug("Time elapsed sensor initiating...")
                    new_sensor = RepetierSensor('elapsed', {'name': printers[id]['slug'],
                                                              'id': id,
                                                              'server': {'url': url, 'port': port, 'apikey': apikey},
                                                              'sens_type': sens_type})
                    devices.append(new_sensor)

        add_entities(devices, True)

    _addDevice()

class RepetierSensor(Entity):
    """Class to create and populate a Repetier Sensor"""

    def __init__(self, type, data):
        """Init new sensor"""
        self._name = data['name']
        self._sens_type = data['sens_type']
        self._type = type
        self._server = data['server']
        self._id = data['id']
        if type == 'nozzle':
            self._nozzle = data['nozzle']
            self._setpoint = None
            self._name = self._name + '_nozzle_' + str(self._nozzle)
        elif type == 'bed':
            self._bed = data['bed']
            self._setpoint = None
            self._name = self._name + '_bed_' + str(self._bed)
        elif type == 'percentage':
            self._name = self._name + '_current_job'
            self._jobname = None
            self._jobid = None
            self._totallines = None
            self._linessent = None
        elif type == 'remaining':
            self._name = self._name + '_current_job_remaining'
            self._endtime = None
            self._secs = None
        elif type == 'elapsed':
            self._name = self._name + '_current_job_elapsed'
            self._starttime = None
            self._secs = None
        self._icon = SENSOR_TYPES[self._sens_type][2]
        self._unit_of_measurement = SENSOR_TYPES[self._sens_type][1]
        self._state = None
        self._attributes = None
        _LOGGER.debug("Created new Repetier Sensor for %s, Type: %s", self._name, self._type)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return sensor state"""
        sens_unit = self.unit_of_measurement
        if self._type == 'nozzle' or self._type == 'bed':
            if self._state is None:
                self._state = 0
            return round(self._state, 2)
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Attributes of this sensor"""
        if self._type == 'nozzle' or self._type == 'bed':
            self._attributes = {'setpoint': self._setpoint}
        elif self._type == 'percentage':
            self._attributes = {'job name': self._jobname,
                                'job id': self._jobid,
                                'total lines': self._totallines,
                                'lines sent': self._linessent}
        elif self._type == 'remaining':
            self._attributes = {'finished:': self._endtime,
                                'seconds': self._secs}
        elif self._type == 'elapsed':
            self._attributes = {'started': self._starttime,
                                'seconds': self._secs}

        return self._attributes

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update the sensor"""
        import pyrepetier
        import time
        server = pyrepetier.Repetier(url=self._server['url'],
                                     port=self._server['port'],
                                     apikey=self._server['apikey'])
        printers = server.getPrinters()
        if self._type == 'nozzle':
            nozzle = server.Nozzle(self._id)
            _LOGGER.debug(nozzle)
            if nozzle != None:
                _LOGGER.debug("Nozzle %s Setpoint: %s, Temp: %s", self._nozzle, nozzle[self._nozzle]['tempset'], nozzle[self._nozzle]['temp']) 
                self._setpoint = nozzle[self._nozzle]['tempset']
                self._state = nozzle[self._nozzle]['temp']
            else:
                _LOGGER.debug("Nozzle %s not found - is printer offline?", self._nozzle)
                self._setpoint = None
                self._state = None
        elif self._type == 'bed':
            bed = server.Bed(self._id)
            if bed != None:
                _LOGGER.debug("Bed %s Setpoint: %s, Temp: %s", self._bed, bed[self._bed]['tempset'], bed[self._bed]['temp'])
                self._setpoint = bed[self._bed]['tempset']
                self._state = bed[self._bed]['temp']
            else:
                _LOGGER.debug("Bed %s not found - is printer offline?", self._bed)
                self._setpoint = None
                self._state = None
        elif self._type == 'state':
            state = server.State(self._id)
            _LOGGER.debug("Printer %s current state: %s", self._name, state)
            self._state = state
        elif self._type == 'percentage':
            state = server.Percent(self._id)
            if state != None:
                self._state = round(state, 1)
                self._jobname = server.JobName(self._id)
                self._jobid = server.JobID(self._id)
                self._totallines = server.TotalLines(self._id)
                self._linessent = server.LinesSent(self._id)
        elif self._type == 'remaining':
            start = server.TimeStart(self._id)
            end = server.PrintLength(self._id)
            printtime = server.PrintTime(self._id)
            if start != None and end != None and printtime != None:
                remaining = end - printtime
                timeend = start + round(end, 0)
                self._secs = int(round(remaining, 0))
                self._endtime = datetime.utcfromtimestamp(timeend).strftime('%Y-%m-%d %H:%M:%S')
                self._state = time.strftime('%H:%M:%S', time.gmtime(self._secs))
        elif self._type == 'elapsed':
            start = server.TimeStart(self._id)
            printtime = server.PrintTime(self._id)
            if start != None and printtime != None:
                self._starttime = datetime.utcfromtimestamp(start).strftime('%Y-%m-%d %H:%M:%S')
                self._secs = int(round(printtime, 0))
                self._state = time.strftime('%H:%M:%S', time.gmtime(self._secs))

