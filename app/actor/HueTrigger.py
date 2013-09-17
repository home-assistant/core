import logging

from phue import Bridge

from app.observer.WeatherWatcher import STATE_CATEGORY_SUN, SOLAR_STATE_BELOW_HORIZON
from app.StateMachine import track_state_change
from app.observer.DeviceTracker import STATE_CATEGORY_ALL_DEVICES, STATE_H, STATE_H5, STATE_NH

class HueTrigger:
	def __init__(self, config, eventbus, statemachine, device_tracker):
		self.statemachine = statemachine
		self.bridge = Bridge(config.get("hue","host"))
		self.lights = self.bridge.get_light_objects()
		self.logger = logging.getLogger("HueTrigger")

		for category in device_tracker.device_state_categories():
			track_state_change(eventbus, category, '*', STATE_H, self.handle_state_change)

		# Track when all devices are gone to shut down lights
		track_state_change(eventbus, STATE_CATEGORY_ALL_DEVICES, [STATE_H,STATE_H5], STATE_NH, self.handle_state_change)

	def handle_state_change(self, category, oldState, newState):
		# print "Hue Trigger - {}: {}->{}".format(category, oldState, newState)

		lights_are_on = sum([1 for light in self.lights if light.on]) > 0

		light_needed = not lights_are_on and self.statemachine.get_state(STATE_CATEGORY_SUN) == SOLAR_STATE_BELOW_HORIZON

		if newState == STATE_H and light_needed:
			self.logger.info("Home coming event for {}. Turning lights on".format(category))
			self.bridge.set_light([1,2,3], 'on', True)
			self.bridge.set_light([1,2,3], 'xy', [0.4595, 0.4105])

		elif newState == STATE_NH and lights_are_on:
			self.logger.info("Everyone has left. Turning lights off")
			self.bridge.set_light([1,2,3], 'on', False)


