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
import re
import json

import requests
import ephem

from . import track_time_change

STATE_CATEGORY_SUN = "weather.sun"
STATE_CATEGORY_NEXT_SUN_RISING = "weather.next_sun_rising"
STATE_CATEGORY_NEXT_SUN_SETTING = "weather.next_sun_setting"
STATE_CATEGORY_ALL_DEVICES = 'all_devices'
STATE_CATEGORY_DEVICE_FORMAT = '{}'

SUN_STATE_ABOVE_HORIZON = "above_horizon"
SUN_STATE_BELOW_HORIZON = "below_horizon"

DEVICE_STATE_NOT_HOME = 'device_not_home'
DEVICE_STATE_HOME = 'device_home'

# After how much time do we consider a device not home if
# it does not show up on scans
TOMATO_TIME_SPAN_FOR_ERROR_IN_SCANNING = timedelta(minutes=1)
TOMATO_MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)
TOMATO_KNOWN_DEVICES_FILE = "tomato_known_devices.csv"


def track_sun(eventbus, statemachine, latitude, longitude):
    """ Tracks the state of the sun. """

    sun = ephem.Sun()
    logger = logging.getLogger(__name__)

    def update_sun_state(now):
        """ Method to update the current state of the sun and time the next update. """
        observer = ephem.Observer()
        observer.lat = latitude
        observer.long = longitude

        next_rising = ephem.localtime(observer.next_rising(sun))
        next_setting = ephem.localtime(observer.next_setting(sun))

        if next_rising > next_setting:
            new_state = SUN_STATE_ABOVE_HORIZON
            next_change = next_setting

        else:
            new_state = SUN_STATE_BELOW_HORIZON
            next_change = next_rising

        logger.info("Sun:{}. Next change: {}".format(new_state, next_change.strftime("%H:%M")))

        statemachine.set_state(STATE_CATEGORY_SUN, new_state)
        statemachine.set_state(STATE_CATEGORY_NEXT_SUN_RISING, next_rising.isoformat())
        statemachine.set_state(STATE_CATEGORY_NEXT_SUN_SETTING, next_setting.isoformat())

        # +10 seconds to be sure that the change has occured
        track_time_change(eventbus, update_sun_state, point_in_time=next_change + timedelta(seconds=10))

    update_sun_state(None)


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
            self.statemachine.set_state(self.devices_to_track[device]['category'], new_state)

        # Update all devices state
        statemachine.set_state(STATE_CATEGORY_ALL_DEVICES, DEVICE_STATE_HOME if len(initial_search) > 0 else DEVICE_STATE_NOT_HOME)

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

        self.date_updated = None
        self.last_results = None

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
            Returns boolean if scanning successful. """

        self.lock.acquire()

        # if date_updated is not defined (update has never ran) or the date is too old we scan for new data
        if self.date_updated is None or datetime.now() - self.date_updated > TOMATO_MIN_TIME_BETWEEN_SCANS:
            self.logger.info("Tomato:Scanning")

            try:
                req = requests.post('http://{}/update.cgi'.format(self.host),
                                                        data={'_http_id':self.http_id, 'exec':'devlist'},
                                                        auth=requests.auth.HTTPBasicAuth(self.username, self.password))

                # Calling and parsing the Tomato api here. We only need the wldev and dhcpd_lease values.
                # See http://paulusschoutsen.nl/blog/2013/10/tomato-api-documentation/ for what's going on here.
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
                # If we could not connect to the router
                self.logger.exception("Tomato:Failed to connect to the router")

                return False

            except ValueError:
                # If json decoder could not parse the response
                self.logger.exception("Tomato:Failed to parse response from router")

                return False

            except IOError:
                # If scanning was successful but we failed to be able to write to the known devices file
                self.logger.exception("Tomato:Updating {} failed".format(TOMATO_KNOWN_DEVICES_FILE))

                return True

            finally:
                self.lock.release()

        else:
            # We acquired the lock before the IF check, release it before we return True
            self.lock.release()


        return True
