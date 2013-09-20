from datetime import datetime
import threading
import time

from app.EventBus import Event
from app.util import ensure_list, matcher

TIME_INTERVAL = 10 # seconds

assert 60 % TIME_INTERVAL == 0, "60 % TIME_INTERVAL should be 0!"

EVENT_TIME_CHANGED = "time_changed"

class Timer(threading.Thread):
    def __init__(self, eventbus):
        threading.Thread.__init__(self)

        self.eventbus = eventbus
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def run(self):
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


def track_time_change(eventBus, action, year='*', month='*', day='*', hour='*', minute='*', second='*', point_in_time=None, listen_once=False):
    year, month, day = ensure_list(year), ensure_list(month), ensure_list(day)
    hour, minute, second = ensure_list(hour), ensure_list(minute), ensure_list(second)

    def listener(event):
        assert isinstance(event, Event), "event needs to be of Event type"

        if  (point_in_time is not None and event.data['now'] > point_in_time) or \
                point_in_time is None and \
                matcher(event.data['now'].year, year) and \
                matcher(event.data['now'].month, month) and \
                matcher(event.data['now'].day, day) and \
                matcher(event.data['now'].hour, hour) and \
                matcher(event.data['now'].minute, minute) and \
                matcher(event.data['now'].second, second):

            # point_in_time are exact points in time so we always remove it after fire
            event.remove_listener = listen_once or point_in_time is not None

            action(event.data['now'])

    eventBus.listen(EVENT_TIME_CHANGED, listener)
