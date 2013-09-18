import logging
from datetime import datetime, timedelta

import ephem

from app.EventBus import Event

from app.observer.Timer import track_time_change

PRE_SUN_SET_WARNING_TIME = 20 # minutes

EVENT_PRE_SUN_SET_WARNING = "sun_set_soon"

STATE_CATEGORY_TEMPLATE_SOLAR = "solar.{}"

STATE_CATEGORY_SUN = STATE_CATEGORY_TEMPLATE_SOLAR.format("sun")

SOLAR_STATE_ABOVE_HORIZON = "above_horizon"
SOLAR_STATE_BELOW_HORIZON = "below_horizon"

class WeatherWatcher:
	def __init__(self, config, eventbus, statemachine): 
		self.logger = logging.getLogger("WeatherWatcher")		
		self.config = config
		self.eventbus = eventbus
		self.statemachine = statemachine

		statemachine.add_category(STATE_CATEGORY_SUN, SOLAR_STATE_BELOW_HORIZON)

		self.update_sun_state()

	def update_sun_state(self, now=datetime.now()):
		self.update_solar_state(ephem.Sun(), STATE_CATEGORY_SUN, self.update_sun_state)

	def update_solar_state(self, solar_body, state_category, update_callback):
		# We don't cache these objects because we use them so rarely
		observer = ephem.Observer()
		observer.lat = self.config.get('common','latitude')
		observer.long = self.config.get('common','longitude')

		next_rising = ephem.localtime(observer.next_rising(solar_body))
		next_setting = ephem.localtime(observer.next_setting(solar_body))

		if next_rising > next_setting:
			new_state = SOLAR_STATE_ABOVE_HORIZON
			next_change = next_setting

		else:
			new_state = SOLAR_STATE_BELOW_HORIZON
			next_change = next_rising

		self.logger.info("Updating solar state for {} to {}. Next change: {}".format(state_category, new_state, next_change))

		self.statemachine.set_state(state_category, new_state)

		# +10 seconds to be sure that the change has occured
		track_time_change(self.eventbus, update_callback, datetime=next_change + timedelta(seconds=10))

		# If the sun is visible, schedule to fire an event X minutes before sun set
		if solar_body.name == 'Sun' and new_state == SOLAR_STATE_ABOVE_HORIZON:
			track_time_change(self.eventbus, lambda time: self.eventbus.fire(Event(EVENT_PRE_SUN_SET_WARNING, {'sun_setting':next_change})), 
								datetime=next_change - timedelta(minutes=PRE_SUN_SET_WARNING_TIME))
		

