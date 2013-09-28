"""
homeassistant.observers
~~~~~~~~~~~~~~~~~~~~~~~

This module provides observers that can change the state or fire
events based on observations.

"""

import logging
import csv
import os
from datetime import datetime, timedelta
import threading
import time
import re
import json

import requests
import ephem

from .core import ensure_list, matcher, Event, EVENT_START, EVENT_SHUTDOWN

TIMER_INTERVAL = 10 # seconds

# We want to be able to fire every time a minute starts (seconds=0).
# We want this so other modules can use that to make sure they fire
# every minute.
assert 60 % TIMER_INTERVAL == 0, "60 % TIMER_INTERVAL should be 0!"


EVENT_TIME_CHANGED = "time_changed"


STATE_CATEGORY_SUN = "weather.sun"
STATE_CATEGORY_ALL_DEVICES = 'device.alldevices'
STATE_CATEGORY_DEVICE_FORMAT = 'device.{}'

SUN_STATE_ABOVE_HORIZON = "above_horizon"
SUN_STATE_BELOW_HORIZON = "below_horizon"

DEVICE_STATE_NOT_HOME = 'device_not_home'
DEVICE_STATE_HOME = 'device_home'


# After how much time do we consider a device not home if
# it does not show up on scans
TOMATO_TIME_SPAN_FOR_ERROR_IN_SCANNING = timedelta(minutes=1)
TOMATO_MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)
TOMATO_KNOWN_DEVICES_FILE = "tomato_known_devices.csv"


class Timer(threading.Thread):
    """ Timer will sent out an event every TIMER_INTERVAL seconds. """

    def __init__(self, eventbus):
        threading.Thread.__init__(self)

        self.eventbus = eventbus
        self._stop = threading.Event()

        eventbus.listen(EVENT_START, lambda event: self.start())
        eventbus.listen(EVENT_SHUTDOWN, lambda event: self._stop.set())

    def run(self):
        """ Start the timer. """

        logging.getLogger(__name__).info("Timer:starting")

        now = datetime.now()

        while True:
            while True:
                time.sleep(1)

                now = datetime.now()

                if self._stop.isSet() or now.second % TIMER_INTERVAL == 0:
                    break

            if self._stop.isSet():
                break

            self.eventbus.fire(Event(EVENT_TIME_CHANGED, {'now':now}))


def track_time_change(eventbus, action, year='*', month='*', day='*', hour='*', minute='*', second='*', point_in_time=None, listen_once=False):
    """ Adds a listener that will listen for a specified or matching time. """
    year, month, day = ensure_list(year), ensure_list(month), ensure_list(day)
    hour, minute, second = ensure_list(hour), ensure_list(minute), ensure_list(second)

    def listener(event):
        """ Listens for matching time_changed events. """
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


class WeatherWatcher(object):
    """ Class that keeps track of the state of the sun. """

    def __init__(self, eventbus, statemachine, latitude, longitude):
        self.logger = logging.getLogger(__name__)
        self.eventbus = eventbus
        self.statemachine = statemachine
        self.latitude = latitude
        self.longitude = longitude

        self.sun = ephem.Sun()

        self._update_sun_state(create_state=True)


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


    def _update_sun_state(self, now=None, create_state=False):
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

        if create_state:
            self.statemachine.add_category(STATE_CATEGORY_SUN, new_state)

        else:
            self.statemachine.set_state(STATE_CATEGORY_SUN, new_state)

        # +10 seconds to be sure that the change has occured
        track_time_change(self.eventbus, self._update_sun_state, point_in_time=next_change + timedelta(seconds=10))


    def _get_observer(self):
        """ Creates an observer representing the location and the current time. """
        observer = ephem.Observer()
        observer.lat = self.latitude
        observer.long = self.longitude

        return observer

class DeviceTracker(object):
    """ Class that tracks which devices are home and which are not. """

    def __init__(self, eventbus, statemachine, device_scanner):
        self.statemachine = statemachine
        self.eventbus = eventbus

        temp_devices_to_track = device_scanner.get_devices_to_track()

        self.devices_to_track = { device: { 'name': temp_devices_to_track[device],
                                            'category': STATE_CATEGORY_DEVICE_FORMAT.format(temp_devices_to_track[device]) }
                                  for device in temp_devices_to_track }

        # Add categories to state machine and update last_seen attribute
        initial_search = device_scanner.get_active_devices()

        default_last_seen = datetime(1990, 1, 1)

        for device in self.devices_to_track:
            if device in initial_search:
                new_state = DEVICE_STATE_HOME
                new_last_seen = datetime.now()
            else:
                new_state = DEVICE_STATE_NOT_HOME
                new_last_seen = default_last_seen

            self.devices_to_track[device]['last_seen'] = new_last_seen
            self.statemachine.add_category(self.devices_to_track[device]['category'], new_state)

        # Update all devices state
        statemachine.add_category(STATE_CATEGORY_ALL_DEVICES, DEVICE_STATE_HOME if len(initial_search) > 0 else DEVICE_STATE_NOT_HOME)

        track_time_change(eventbus, lambda time: self.update_devices(device_scanner.get_active_devices()))


    def device_state_categories(self):
        """ Returns a list of categories of devices that are being tracked by this class. """
        return [self.devices_to_track[device]['category'] for device in self.devices_to_track]


    def update_devices(self, found_devices):
        """ Keep track of devices that are home, all that are not will be marked not home. """

        temp_tracking_devices = self.devices_to_track.keys()

        for device in found_devices:
            # Are we tracking this device?
            if device in temp_tracking_devices:
                temp_tracking_devices.remove(device)

                self.devices_to_track[device]['last_seen'] = datetime.now()
                self.statemachine.set_state(self.devices_to_track[device]['category'], DEVICE_STATE_HOME)

        # For all devices we did not find, set state to NH
        # But only if they have been gone for longer then the error time span
        # Because we do not want to have stuff happening when the device does
        # not show up for 1 scan beacuse of reboot etc
        for device in temp_tracking_devices:
            if datetime.now() - self.devices_to_track[device]['last_seen'] > TOMATO_TIME_SPAN_FOR_ERROR_IN_SCANNING:
                self.statemachine.set_state(self.devices_to_track[device]['category'], DEVICE_STATE_NOT_HOME)

        # Get the currently used statuses
        states_of_devices = [self.statemachine.get_state(self.devices_to_track[device]['category']).state for device in self.devices_to_track]

        all_devices_state = DEVICE_STATE_HOME if DEVICE_STATE_HOME in states_of_devices else DEVICE_STATE_NOT_HOME

        self.statemachine.set_state(STATE_CATEGORY_ALL_DEVICES, all_devices_state)

class TomatoDeviceScanner(object):
    """ This class tracks devices connected to a wireless router running Tomato firmware. """

    def __init__(self, host, username, password, http_id):
        self.host = host
        self.username = username
        self.password = password
        self.http_id = http_id

        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()

        # Read known devices if file exists
        if os.path.isfile(TOMATO_KNOWN_DEVICES_FILE):
            with open(TOMATO_KNOWN_DEVICES_FILE) as inp:
                self.known_devices = { row['mac']: row for row in csv.DictReader(inp) }

        # Create a dict with ID: NAME of the devices to track
        self.devices_to_track = {mac: info['name'] for mac, info in self.known_devices.items() if info['track'] == '1'}

        if len(self.devices_to_track) == 0:
            self.logger.warning("No devices to track. Please update {}.".format(TOMATO_KNOWN_DEVICES_FILE))

    def get_devices_to_track(self):
        """ Returns a ``dict`` with device_id: device_name values. """
        return self.devices_to_track

    def get_active_devices(self):
        """ Scans for new devices and returns a list containing device_ids. """
        self._update_tomato_info()

        return [item[1] for item in self.last_results['wldev']]

    def _update_tomato_info(self):
        """ Ensures the information from the Tomato router is up to date.
            Returns boolean if successful. """

        # if date_updated is not defined (update has never ran) or the date is too old we scan for new data
        if not hasattr(self,'date_updated') or datetime.now() - self.date_updated > TOMATO_MIN_TIME_BETWEEN_SCANS:
            self.lock.acquire()

            self.logger.info("Tomato:Scanning")

            try:
                req = requests.post('http://{}/update.cgi'.format(self.host),
                                                        data={'_http_id':self.http_id, 'exec':'devlist'},
                                                        auth=requests.auth.HTTPBasicAuth(self.username, self.password))

                """
                Tomato API:
                arplist contains a list of lists with items:
                 - ip (string)
                 - mac (string)
                 - iface (string)

                wldev contains list of lists with items:
                 - iface (string)
                 - mac (string)
                 - rssi (int)
                 - tx (int)
                 - rx (int)
                 - quality (int)
                 - unknown_num (int)

                dhcpd_lease contains a list of lists with items:
                 - name (string)
                 - ip (string)
                 - mac (string)
                 - lease_age (string)
                """
                self.last_results = {param: json.loads(value.replace("'",'"'))
                                     for param, value in re.findall(r"(?P<param>\w*) = (?P<value>.*);", req.text)
                                     if param in ["wldev","dhcpd_lease"]}

                self.date_updated = datetime.now()

                # If we come along any unknown devices we will write them to the known devices file
                unknown_devices = [(name, mac) for name, _, mac, _ in self.last_results['dhcpd_lease'] if mac not in self.known_devices]

                if len(unknown_devices) > 0:
                    self.logger.info("Tomato:Found {} new devices, updating {}".format(len(unknown_devices), TOMATO_KNOWN_DEVICES_FILE))

                    with open(TOMATO_KNOWN_DEVICES_FILE, 'a') as outp:
                        writer = csv.writer(outp)

                        for name, mac in unknown_devices:
                            writer.writerow((mac, name, 0))
                            self.known_devices[mac] = {'name':name, 'track': '0'}

            except requests.ConnectionError:
                self.logger.exception("Tomato:Scanning failed")

                return False

            except IOError:
                self.logger.exception("Tomato:Updating {} failed".format(TOMATO_KNOWN_DEVICES_FILE))

                return True

            finally:
                self.lock.release()


        return True
