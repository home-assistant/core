import logging
from datetime import timedelta

import ephem

from app.observer.Timer import track_time_change

STATE_CATEGORY_SUN = "weather.sun"

SUN_STATE_ABOVE_HORIZON = "above_horizon"
SUN_STATE_BELOW_HORIZON = "below_horizon"

class WeatherWatcher(object):
    def __init__(self, config, eventbus, statemachine):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.eventbus = eventbus
        self.statemachine = statemachine

        self.observer = ephem.Observer()
        self.observer.lat = self.config.get('common','latitude')
        self.observer.long = self.config.get('common','longitude')

        self.sun = ephem.Sun()

        statemachine.add_category(STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON)

        self.update_sun_state()

    def next_sun_rising(self):
        return ephem.localtime(self.observer.next_rising(self.sun))

    def next_sun_setting(self):
        return ephem.localtime(self.observer.next_setting(self.sun))

    def update_sun_state(self, now=None):
        next_rising = ephem.localtime(self.observer.next_rising(self.sun))
        next_setting = ephem.localtime(self.observer.next_setting(self.sun))

        if next_rising > next_setting:
            new_state = SUN_STATE_ABOVE_HORIZON
            next_change = next_setting

        else:
            new_state = SUN_STATE_BELOW_HORIZON
            next_change = next_rising

        self.logger.info("Updating sun state to {}. Next change: {}".format(new_state, next_change))

        self.statemachine.set_state(STATE_CATEGORY_SUN, new_state)

        # +10 seconds to be sure that the change has occured
        track_time_change(self.eventbus, self.update_sun_state, point_in_time=next_change + timedelta(seconds=10))
