import logging
from datetime import datetime

from phue import Bridge

from app.observer.WeatherWatcher import EVENT_PRE_SUN_SET_WARNING, STATE_CATEGORY_SUN, SOLAR_STATE_BELOW_HORIZON
from app.StateMachine import track_state_change
from app.DeviceTracker import STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME, STATE_DEVICE_NOT_HOME

class HueTrigger:
	def __init__(self, config, eventbus, statemachine, device_tracker):
		self.statemachine = statemachine

		self.bridge = Bridge(config.get("hue","host"))
		self.lights = self.bridge.get_light_objects()
		self.logger = logging.getLogger("HueTrigger")

		# Track home coming of each seperate device
		for category in device_tracker.device_state_categories():
			track_state_change(eventbus, category, STATE_DEVICE_NOT_HOME, STATE_DEVICE_HOME, self.handle_device_state_change)

		# Track when all devices are gone to shut down lights
		track_state_change(eventbus, STATE_CATEGORY_ALL_DEVICES, STATE_DEVICE_HOME, STATE_DEVICE_NOT_HOME, self.handle_device_state_change)

		# Listen for when sun is about to set
		eventbus.listen(EVENT_PRE_SUN_SET_WARNING, self.handle_sun_setting)


	def get_lights_status(self):
		lights_are_on = sum([1 for light in self.lights if light.on]) > 0

		light_needed = not lights_are_on and self.statemachine.get_state(STATE_CATEGORY_SUN).state == SOLAR_STATE_BELOW_HORIZON

		return lights_are_on, light_needed


	def turn_lights_on(self, transitiontime=None):
		command = {'on': True, 'xy': [0.5119, 0.4147], 'bri':164}

		if transitiontime is not None:
			command['transitiontime'] = transitiontime

		self.bridge.set_light([1,2,3], command)


	def turn_lights_off(self, transitiontime=None):
		command = {'on': False}

		if transitiontime is not None:
			command['transitiontime'] = transitiontime

		self.bridge.set_light([1,2,3], command)


	# Gets called when darkness starts falling in, slowly turn on the lights
	def handle_sun_setting(self, event):
		lights_are_on, light_needed = self.get_lights_status()

		if light_needed and self.statemachine.get_state(STATE_CATEGORY_ALL_DEVICES).state == STATE_DEVICE_HOME:
			self.logger.info("Sun setting and devices home. Turning on lights.")

			# We will start the lights now and by the time the sun sets
			# the lights will be at full brightness
			transitiontime = (event.data['sun_setting'] - datetime.now()).seconds * 10

			self.turn_lights_on(transitiontime)


	def handle_device_state_change(self, category, oldState, newState):
		lights_are_on, light_needed = self.get_lights_status()

		# Specific device came home ?
		if category != STATE_CATEGORY_ALL_DEVICES and newState.state == STATE_DEVICE_HOME and light_needed:
			self.logger.info("Home coming event for {}. Turning lights on".format(category))
			self.turn_lights_on()

		# Did all devices leave the house?
		elif category == STATE_CATEGORY_ALL_DEVICES and newState.state == STATE_DEVICE_NOT_HOME and lights_are_on:
			self.logger.info("Everyone has left. Turning lights off")
			self.turn_lights_off()


