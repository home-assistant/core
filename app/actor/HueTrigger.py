import logging

from phue import Bridge

from app.observer.WeatherWatcher import STATE_CATEGORY_SUN, SOLAR_STATE_BELOW_HORIZON, SOLAR_STATE_ABOVE_HORIZON
from app.StateMachine import track_state_change
from app.observer.DeviceTracker import STATE_CATEGORY_ALL_DEVICES, STATE_H, STATE_H5, STATE_NH

class HueTrigger:
	def __init__(self, config, eventbus, statemachine, device_tracker):
		self.statemachine = statemachine
		self.bridge = Bridge(config.get("hue","host"))
		self.lights = self.bridge.get_light_objects()
		self.logger = logging.getLogger("HueTrigger")

		for category in device_tracker.device_state_categories():
			track_state_change(eventbus, category, '*', STATE_H, self.handle_device_state_change)

		# Track when all devices are gone to shut down lights
		track_state_change(eventbus, STATE_CATEGORY_ALL_DEVICES, [STATE_H,STATE_H5], STATE_NH, self.handle_device_state_change)

		# Track when sun sets
		track_state_change(eventbus, STATE_CATEGORY_SUN, SOLAR_STATE_ABOVE_HORIZON, SOLAR_STATE_BELOW_HORIZON, self.handle_sun_state_change)


	def get_lights_status(self):
		lights_are_on = sum([1 for light in self.lights if light.on]) > 0

		light_needed = not lights_are_on and self.statemachine.get_state(STATE_CATEGORY_SUN) == SOLAR_STATE_BELOW_HORIZON

		return lights_are_on, light_needed


	def turn_lights_on(self):
		self.bridge.set_light([1,2,3], 'on', True)
		self.bridge.set_light([1,2,3], 'xy', [0.4595, 0.4105])


	def turn_lights_off(self):
		self.bridge.set_light([1,2,3], 'on', False)


	# If sun sets, the lights are 
	def handle_sun_state_change(self, category, oldState, newState):
		lights_are_on, light_needed = self.get_lights_status()

		if light_needed and self.statemachine.get_state(STATE_CATEGORY_ALL_DEVICES) in [STATE_H, STATE_H5]:
			self.turn_lights_on()


	def handle_device_state_change(self, category, oldState, newState):
		lights_are_on, light_needed = self.get_lights_status()

		# Specific device came home ?
		if category != STATE_CATEGORY_ALL_DEVICES and newState == STATE_H and light_needed:
			self.logger.info("Home coming event for {}. Turning lights on".format(category))
			self.turn_lights_on()

		# Did all devices leave the house?
		elif category == STATE_CATEGORY_ALL_DEVICES and newState == STATE_NH and lights_are_on:
			self.logger.info("Everyone has left. Turning lights off")
			self.turn_lights_off()


