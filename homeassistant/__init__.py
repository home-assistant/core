"""
homeassistant
~~~~~~~~~~~~~

Module to control the lights based on devices at home and the state of the sun.

"""

import logging
import time

from .core import EventBus, StateMachine, Event, EVENT_START, EVENT_SHUTDOWN
from .httpinterface import HTTPInterface
from .observers import DeviceTracker, WeatherWatcher, Timer
from .actors import LightTrigger



class HomeAssistant(object):
    """ Class to tie all modules together and handle dependencies. """

    def __init__(self, latitude=None, longitude=None):
        self.latitude = latitude
        self.longitude = longitude

        self.logger = logging.getLogger(__name__)

        self.eventbus = EventBus()
        self.statemachine = StateMachine(self.eventbus)

        self.httpinterface = None
        self.weatherwatcher = None

    def setup_light_trigger(self, device_scanner, light_control):
        """ Sets up the light trigger system. """
        self.logger.info("Setting up light trigger")

        devicetracker = DeviceTracker(self.eventbus, self.statemachine, device_scanner)

        LightTrigger(self.eventbus, self.statemachine, self._setup_weather_watcher(), devicetracker, light_control)


    def setup_http_interface(self):
        """ Sets up the HTTP interface. """
        if self.httpinterface is None:
            self.logger.info("Setting up HTTP interface")
            self.httpinterface = HTTPInterface(self.eventbus, self.statemachine)

        return self.httpinterface


    def start(self):
        """ Start home assistant. """
        Timer(self.eventbus)

        self.eventbus.fire(Event(EVENT_START))

        while True:
            try:
                time.sleep(1)

            except KeyboardInterrupt:
                print ""
                self.eventbus.fire(Event(EVENT_SHUTDOWN))

                break

    def _setup_weather_watcher(self):
        """ Sets up the weather watcher. """
        if self.weatherwatcher is None:
            self.weatherwatcher = WeatherWatcher(self.eventbus, self.statemachine, self.latitude, self.longitude)

        return self.weatherwatcher


