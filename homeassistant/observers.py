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
TIME_SPAN_FOR_ERROR_IN_SCANNING = timedelta(minutes=1)

# Return cached results if last scan was less then this time ago
TOMATO_MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

# Filename to save known devices to
KNOWN_DEVICES_FILE = "known_devices.csv"


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
        self.device_scanner = device_scanner
        self.logger = logging.getLogger(__name__)

        self.lock = threading.Lock()

        # Dictionary to keep track of known devices and devices we track
        self.known_devices = {}

        # Did we encounter a valid known devices file
        self.invalid_known_devices_file = False

        # Read known devices if file exists
        if os.path.isfile(KNOWN_DEVICES_FILE):
            with open(KNOWN_DEVICES_FILE) as inp:
                default_last_seen = datetime(1990, 1, 1)

                # Temp variable to keep track of which categories we use
                # so we can ensure we have unique categories.
                used_categories = []

                try:
                    for row in csv.DictReader(inp):
                        device = row['device']

                        row['track'] = True if row['track'] == '1' else False

                        self.known_devices[device] = row

                        # If we track this device setup tracking variables
                        if row['track']:
                            self.known_devices[device]['last_seen'] = default_last_seen

                            # Make sure that each device is mapped to a unique category name
                            name = row['name'] if row['name'] else "unnamed_device"

                            tries = 0

                            while True:
                                tries += 1

                                category = STATE_CATEGORY_DEVICE_FORMAT.format(name if tries == 1 else "{}_{}".format(name, tries))

                                if category not in used_categories:
                                    break

                            self.known_devices[device]['category'] = category
                            used_categories.append(category)

                except KeyError:
                    self.invalid_known_devices_file = False
                    self.logger.warning("Invalid {} found. We won't update it with new found devices.".format(KNOWN_DEVICES_FILE))

        if len(self.device_state_categories()) == 0:
            self.logger.warning("No devices to track. Please update {}.".format(KNOWN_DEVICES_FILE))


        track_time_change(eventbus, lambda time: self.update_devices(device_scanner.scan_devices()))

    def device_state_categories(self):
        """ Returns a list containing all categories that are maintained for devices. """
        return [self.known_devices[device]['category'] for device in self.known_devices if self.known_devices[device]['track']]

    def update_devices(self, found_devices):
        """ Keep track of devices that are home, all that are not will be marked not home. """
        self.lock.acquire()

        temp_tracking_devices = [device for device in self.known_devices if self.known_devices[device]['track']]

        for device in found_devices:
            # Are we tracking this device?
            if device in temp_tracking_devices:
                temp_tracking_devices.remove(device)

                self.known_devices[device]['last_seen'] = datetime.now()
                self.statemachine.set_state(self.known_devices[device]['category'], DEVICE_STATE_HOME)

        # For all devices we did not find, set state to NH
        # But only if they have been gone for longer then the error time span
        # Because we do not want to have stuff happening when the device does
        # not show up for 1 scan beacuse of reboot etc
        for device in temp_tracking_devices:
            if datetime.now() - self.known_devices[device]['last_seen'] > TIME_SPAN_FOR_ERROR_IN_SCANNING:
                self.statemachine.set_state(self.known_devices[device]['category'], DEVICE_STATE_NOT_HOME)

        # Get the currently used statuses
        states_of_devices = [self.statemachine.get_state(category).state for category in self.device_state_categories()]

        # Update the all devices category
        all_devices_state = DEVICE_STATE_HOME if DEVICE_STATE_HOME in states_of_devices else DEVICE_STATE_NOT_HOME

        self.statemachine.set_state(STATE_CATEGORY_ALL_DEVICES, all_devices_state)

        # If we come along any unknown devices we will write them to the known devices file
        # but only if we did not encounter an invalid known devices file
        if not self.invalid_known_devices_file:
            unknown_devices = [device for device in found_devices if device not in self.known_devices]

            if len(unknown_devices) > 0:
                try:
                    # If file does not exist we will write the header too
                    should_write_header = not os.path.isfile(KNOWN_DEVICES_FILE)

                    with open(KNOWN_DEVICES_FILE, 'a') as outp:
                        self.logger.info("DeviceTracker:Found {} new devices, updating {}".format(len(unknown_devices), KNOWN_DEVICES_FILE))
                        writer = csv.writer(outp)

                        if should_write_header:
                            writer.writerow(("device", "name", "track"))

                        for device in unknown_devices:
                            # See if the device scanner knows the name
                            temp_name = self.device_scanner.get_device_name(device)
                            name = temp_name if temp_name else "unknown_device"

                            writer.writerow((device, name, 0))
                            self.known_devices[device] = {'name':name, 'track': False}

                except IOError:
                    self.logger.exception("DeviceTracker:Error updating {} with {} new devices".format(KNOWN_DEVICES_FILE, len(unknown_devices)))

        self.lock.release()


class TomatoDeviceScanner(object):
    """ This class queries a wireless router running Tomato firmware for connected devices.

        A description of the Tomato API can be found on
        http://paulusschoutsen.nl/blog/2013/10/tomato-api-documentation/ """

    def __init__(self, host, username, password, http_id):
        self.req = requests.Request('POST', 'http://{}/update.cgi'.format(host),
                                    data={'_http_id':http_id, 'exec':'devlist'},
                                    auth=requests.auth.HTTPBasicAuth(username, password)).prepare()

        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()

        self.date_updated = None
        self.last_results = {"wldev": [], "dhcpd_lease": []}

    def scan_devices(self):
        """ Scans for new devices and returns a list containing found device ids. """

        self._update_tomato_info()

        return [item[1] for item in self.last_results['wldev']]

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """

        # Make sure there are results
        if not self.date_updated:
            self._update_tomato_info()

        filter_named = [item[0] for item in self.last_results['dhcpd_lease'] if item[2] == device]

        return None if len(filter_named) == 0 or filter_named[0] == "" else filter_named[0]

    def _update_tomato_info(self):
        """ Ensures the information from the Tomato router is up to date.
            Returns boolean if scanning successful. """

        self.lock.acquire()

        # if date_updated is None or the date is too old we scan for new data
        if not self.date_updated or datetime.now() - self.date_updated > TOMATO_MIN_TIME_BETWEEN_SCANS:
            self.logger.info("Tomato:Scanning")

            try:
                response = requests.Session().send(self.req)

                # Calling and parsing the Tomato api here. We only need the wldev and dhcpd_lease values.
                # See http://paulusschoutsen.nl/blog/2013/10/tomato-api-documentation/ for what's going on here.
                self.last_results = {param: json.loads(value.replace("'",'"'))
                                     for param, value in re.findall(r"(?P<param>\w*) = (?P<value>.*);", response.text)
                                     if param in ["wldev","dhcpd_lease"]}

                self.date_updated = datetime.now()


            except requests.ConnectionError:
                # If we could not connect to the router
                self.logger.exception("Tomato:Failed to connect to the router")

            except ValueError:
                # If json decoder could not parse the response
                self.logger.exception("Tomato:Failed to parse response from router")

            finally:
                self.lock.release()

        else:
            # We acquired the lock before the IF check, release it before we return True
            self.lock.release()

