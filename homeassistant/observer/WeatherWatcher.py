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

        self.sun = ephem.Sun()

        statemachine.add_category(STATE_CATEGORY_SUN, SUN_STATE_BELOW_HORIZON)

        self._update_sun_state()


    def next_sun_rising(self, observer=None):
        """ Returns a datetime object that points at the next sun rising. """

        if observer is None:
            observer = self._get_observer()

        return ephem.localtime(observer.next_rising(self.sun))


    def next_sun_setting(self, observer=None):
        """ Returns a datetime object that points at the next sun setting. """

        if observer is None:
            observer = self._get_observer()

        return ephem.localtime(observer.next_setting(self.sun))


    def _update_sun_state(self, now=None):
        """ Updates the state of the sun and schedules when to check next. """

        observer = self._get_observer()

        next_rising = self.next_sun_rising(observer)
        next_setting = self.next_sun_setting(observer)

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


    def _get_observer(self):
        """ Creates an observer representing the location from the config and the current time. """
        observer = ephem.Observer()
        observer.lat = self.config.get('common','latitude')
        observer.long = self.config.get('common','longitude')

        return observer
