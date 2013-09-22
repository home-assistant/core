import logging
from ConfigParser import SafeConfigParser
import time

from homeassistant.StateMachine import StateMachine
from homeassistant.EventBus import EventBus
from homeassistant.HttpInterface import HttpInterface

from homeassistant.observer.DeviceTracker import DeviceTracker
from homeassistant.observer.WeatherWatcher import WeatherWatcher
from homeassistant.observer.Timer import Timer

from homeassistant.actor.LightTrigger import LightTrigger

CONFIG_FILE = "home-assistant.conf"

class HomeAssistant(object):
    """ Class to tie all modules together and handle dependencies. """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        self.config = None
        self.eventbus = None
        self.statemachine = None

        self.timer = None
        self.weatherwatcher = None
        self.devicetracker = None

        self.lighttrigger = None
        self.httpinterface = None


    def get_config(self):
        if self.config is None:
            self.logger.info("Loading HomeAssistant config")
            self.config = SafeConfigParser()
            self.config.read(CONFIG_FILE)

        return self.config


    def get_event_bus(self):
        if self.eventbus is None:
            self.logger.info("Setting up event bus")
            self.eventbus = EventBus()

        return self.eventbus


    def get_state_machine(self):
        if self.statemachine is None:
            self.logger.info("Setting up state machine")
            self.statemachine = StateMachine(self.get_event_bus())

        return self.statemachine


    def setup_timer(self):
        if self.timer is None:
            self.logger.info("Setting up timer")
            self.timer = Timer(self.get_event_bus())

        return self.timer


    def setup_weather_watcher(self):
        if self.weatherwatcher is None:
            self.logger.info("Setting up weather watcher")
            self.weatherwatcher = WeatherWatcher(self.get_config(), self.get_event_bus(), self.get_state_machine())

        return self.weatherwatcher


    def setup_device_tracker(self, device_scanner):
        if self.devicetracker is None:
            self.logger.info("Setting up device tracker")
            self.devicetracker = DeviceTracker(self.get_event_bus(), self.get_state_machine(), device_scanner)

        return self.devicetracker


    def setup_light_trigger(self, light_control):
        if self.lighttrigger is None:
            self.logger.info("Setting up light trigger")
            assert self.devicetracker is not None, "Cannot setup light trigger without a device tracker being setup"

            self.lighttrigger = LightTrigger(self.get_event_bus(), self.get_state_machine(), self.devicetracker, self.setup_weather_watcher(), light_control)

        return self.lighttrigger


    def setup_http_interface(self):
        if self.httpinterface is None:
            self.logger.info("Setting up HTTP interface")
            self.httpinterface = HttpInterface(self.get_event_bus(), self.get_state_machine())

        return self.httpinterface


    def start(self):
        self.setup_timer().start()

        if self.httpinterface is not None:
            self.httpinterface.start()

        while True:
            try:
                time.sleep(1)

            except KeyboardInterrupt:
                print ""
                print "Interrupt received. Wrapping up and quiting.."
                self.timer.stop()

                if self.httpinterface is not None:
                    self.httpinterface.stop()

                break
