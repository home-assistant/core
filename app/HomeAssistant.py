from ConfigParser import SafeConfigParser
import time

from app.StateMachine import StateMachine
from app.EventBus import EventBus
from app.DeviceTracker import DeviceTracker

from app.observer.WeatherWatcher import WeatherWatcher
from app.observer.TomatoDeviceScanner import TomatoDeviceScanner
from app.observer.Timer import Timer

from app.actor.HueTrigger import HueTrigger

class HomeAssistant:

	def __init__(self):
		self.config = None
		self.eventbus = None
		self.statemachine = None

		self.timer = None
		self.weatherwatcher = None
		self.devicetracker = None

		self.huetrigger = None


	def get_config(self):
		if self.config is None:
			self.config = SafeConfigParser()
			self.config.read("home-assistant.conf")

		return self.config


	def get_event_bus(self):
		if self.eventbus is None:
			self.eventbus = EventBus()

		return self.eventbus


	def get_state_machine(self):
		if self.statemachine is None:
			self.statemachine = StateMachine(self.get_event_bus())

		return self.statemachine


	def setup_timer(self):
		if self.timer is None:
			self.timer = Timer(self.get_event_bus())

		return self.timer

	def setup_weather_watcher(self):
		if self.weatherwatcher is None:
			self.weatherwatcher = WeatherWatcher(self.get_config(), self.get_event_bus(), self.get_state_machine())

		return self.weatherwatcher


	def setup_device_tracker(self, device_scanner):
		if self.devicetracker is None:
			self.devicetracker = DeviceTracker(self.get_event_bus(), self.get_state_machine(), device_scanner)

		return self.devicetracker


	def setup_hue_trigger(self):
		if self.huetrigger is None:
			assert self.devicetracker is not None, "Cannot setup Hue Trigger without a device tracker being setup"

			self.huetrigger = HueTrigger(self.get_config(), self.get_event_bus(), self.get_state_machine(), self.devicetracker, self.setup_weather_watcher())

		return self.huetrigger


	def start(self):
		self.setup_timer().start()

		while True:
			try:
				time.sleep(1)

			except:
				print ""
				print "Interrupt received. Wrapping up and quiting.."
				self.timer.stop()
				break





