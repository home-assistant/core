"""
homeassistant.components.sensor.verisure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with Verisure sensors.
"""
import logging

import homeassistant.components.verisure as verisure

from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_OPEN, STATE_CLOSED

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Verisure platform. """

    if not verisure.MY_PAGES:
        _LOGGER.error('A connection has not been made to Verisure mypages.')
        return False

    sensors = [
        VerisureClimateDevice(status) for status 
        in verisure.MY_PAGES.get_climate_status()]

    sensors.extend([
        VerisureAlarmDevice(status) for status
        in verisure.MY_PAGES.get_alarm_status()])


    add_devices(sensors)


class VerisureClimateDevice(Entity):
    """ represents a Verisure climate sensor within home assistant. """

    def __init__(self, climate_status):
        self._status = climate_status
    
    @property
    def name(self):
        """ Returns the name of the device. """
        return self._status.location

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._status.temperature


class VerisureAlarmDevice(Entity):
    """ represents a Verisure alarm remote control within home assistant. """
    
    def __init__(self, alarm_status):
        self._status = alarm_status
    
    @property
    def name(self):
        """ Returns the name of the device. """
        return 'Alarm {}'.format(self._status.id)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._status.status
