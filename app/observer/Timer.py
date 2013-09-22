import logging
from datetime import datetime
import threading
import time

from app.EventBus import Event
from app.util import matcher

TIME_INTERVAL = 10 # seconds

# We want to be able to fire every time a minute starts (seconds=0).
# We want this so other modules can use that to make sure they fire
# every minute.
assert 60 % TIME_INTERVAL == 0, "60 % TIME_INTERVAL should be 0!"

EVENT_TIME_CHANGED = "time_changed"

class Timer(threading.Thread):
    """ Timer will sent out an event every TIME_INTERVAL seconds. """

    def __init__(self, eventbus):
        threading.Thread.__init__(self)

        self.eventbus = eventbus
        self._stop = threading.Event()


    def stop(self):
        """ Tell the timer to stop. """
        self._stop.set()


    def run(self):
        """ Start the timer. """
        
        logging.getLogger(__name__).info("Starting")

        now = datetime.now()

        while True:
            if self._stop.isSet():
                break

            self.eventbus.fire(Event(EVENT_TIME_CHANGED, {'now':now}))

            while True:
                time.sleep(1)

                now = datetime.now()

                if self._stop.isSet() or now.second % TIME_INTERVAL == 0:
                    break


def track_time_change(eventbus, action, year='*', month='*', day='*', hour='*', minute='*', second='*', point_in_time=None, listen_once=False):
    year, month, day = list(year), list(month), list(day)
    hour, minute, second = list(hour), list(minute), list(second)

    def listener(event):
        assert isinstance(event, Event), "event needs to be of Event type"

        if  (point_in_time is not None and event.data['now'] > point_in_time) or \
                (point_in_time is None and \
                matcher(event.data['now'].year, year) and \
                matcher(event.data['now'].month, month) and \
                matcher(event.data['now'].day, day) and \
                matcher(event.data['now'].hour, hour) and \
                matcher(event.data['now'].minute, minute) and \
                matcher(event.data['now'].second, second)):

            # point_in_time are exact points in time so we always remove it after fire
            event.remove_listener = listen_once or point_in_time is not None

            action(event.data['now'])

    eventbus.listen(EVENT_TIME_CHANGED, listener)
