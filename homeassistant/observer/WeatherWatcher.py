import logging
from datetime import timedelta

import ephem

from homeassistant.observer.Timer import track_time_change

STATE_CATEGORY_SUN = "weather.sun"

SUN_STATE_ABOVE_HORIZON = "above_horizon"
SUN_STATE_BELOW_HORIZON = "below_horizon"

class WeatherWatcher(object):
    """ Class that keeps track of the state of the sun. """

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

        self._update_sun_state()


    def next_sun_rising(self):
        """ Returns a datetime object that points at the next sun rising. """
        return ephem.localtime(self.observer.next_rising(self.sun))


    def next_sun_setting(self):
        """ Returns a datetime object that points at the next sun setting. """
        return ephem.localtime(self.observer.next_setting(self.sun))


    def _update_sun_state(self, now=None):
        """ Updates the state of the sun and schedules when to check next. """
        next_rising = self.next_sun_rising()
        next_setting = self.next_sun_setting()

        if next_rising > next_setting:
            new_state = SUN_STATE_ABOVE_HORIZON
            next_change = next_setting

        else:
            new_state = SUN_STATE_BELOW_HORIZON
            next_change = next_rising

        self.logger.info("Sun:{}. Next change: {}".format(new_state, next_change.strftime("%H:%M")))

        self.statemachine.set_state(STATE_CATEGORY_SUN, new_state)

        # +10 seconds to be sure that the change has occured
        track_time_change(self.eventbus, self._update_sun_state, point_in_time=next_change + timedelta(seconds=10))
