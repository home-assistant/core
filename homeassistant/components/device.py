"""
homeassistant.components.sun
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to keep track of devices.
"""
import logging
import threading
import os
import csv
import re
import json
from datetime import datetime, timedelta

import requests

import homeassistant as ha
import homeassistant.util as util

DOMAIN_DEVICE_TRACKER = "device_tracker"

SERVICE_DEVICE_TRACKER_RELOAD = "reload_devices_csv"

STATE_CATEGORY_ALL_DEVICES = 'devices'
STATE_CATEGORY_FORMAT = 'devices.{}'

STATE_NOT_HOME = 'device_not_home'
STATE_HOME = 'device_home'


# After how much time do we consider a device not home if
# it does not show up on scans
TIME_SPAN_FOR_ERROR_IN_SCANNING = timedelta(minutes=1)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

# Filename to save known devices to
KNOWN_DEVICES_FILE = "known_devices.csv"


def get_categories(statemachine):
    """ Returns the categories of devices that are being tracked in the
        statemachine. """
    return ha.get_grouped_state_cats(statemachine, STATE_CATEGORY_FORMAT,
                                     False)


def get_ids(statemachine):
    """ Returns the devices that are being tracked in the statemachine. """
    return ha.get_grouped_state_cats(statemachine, STATE_CATEGORY_FORMAT, True)


def is_home(statemachine, device_id=None):
    """ Returns if any or specified device is home. """
    category = STATE_CATEGORY_FORMAT.format(device_id) if device_id \
        else STATE_CATEGORY_ALL_DEVICES

    return statemachine.is_state(category, STATE_HOME)


class DeviceTracker(object):
    """ Class that tracks which devices are home and which are not. """

    def __init__(self, bus, statemachine, device_scanner):
        self.statemachine = statemachine
        self.bus = bus
        self.device_scanner = device_scanner
        self.logger = logging.getLogger(__name__)

        self.lock = threading.Lock()

        # Dictionary to keep track of known devices and devices we track
        self.known_devices = {}

        # Did we encounter a valid known devices file
        self.invalid_known_devices_file = False

        self._read_known_devices_file()

        ha.track_time_change(bus,
                             lambda time:
                             self.update_devices(
                                 device_scanner.scan_devices()))

        bus.register_service(DOMAIN_DEVICE_TRACKER,
                             SERVICE_DEVICE_TRACKER_RELOAD,
                             lambda service: self._read_known_devices_file())

        self.update_devices(device_scanner.scan_devices())

    @property
    def device_state_categories(self):
        """ Returns a set containing all categories
            that are maintained for devices. """
        return set([self.known_devices[device]['category'] for device
                    in self.known_devices
                    if self.known_devices[device]['track']])

    def update_devices(self, found_devices):
        """ Update device states based on the found devices. """
        self.lock.acquire()

        now = datetime.now()

        temp_tracking_devices = [device for device in self.known_devices
                                 if self.known_devices[device]['track']]

        for device in found_devices:
            # Are we tracking this device?
            if device in temp_tracking_devices:
                temp_tracking_devices.remove(device)

                self.known_devices[device]['last_seen'] = now

                self.statemachine.set_state(
                    self.known_devices[device]['category'], STATE_HOME)

        # For all devices we did not find, set state to NH
        # But only if they have been gone for longer then the error time span
        # Because we do not want to have stuff happening when the device does
        # not show up for 1 scan beacuse of reboot etc
        for device in temp_tracking_devices:
            if (now - self.known_devices[device]['last_seen'] >
               TIME_SPAN_FOR_ERROR_IN_SCANNING):

                self.statemachine.set_state(
                    self.known_devices[device]['category'],
                    STATE_NOT_HOME)

        # Get the currently used statuses
        states_of_devices = [self.statemachine.get_state(category)['state']
                             for category in self.device_state_categories]

        # Update the all devices category
        all_devices_state = (STATE_HOME if STATE_HOME
                             in states_of_devices else STATE_NOT_HOME)

        self.statemachine.set_state(STATE_CATEGORY_ALL_DEVICES,
                                    all_devices_state)

        # If we come along any unknown devices we will write them to the
        # known devices file but only if we did not encounter an invalid
        # known devices file
        if not self.invalid_known_devices_file:

            unknown_devices = [device for device in found_devices
                               if device not in self.known_devices]

            if len(unknown_devices) > 0:
                try:
                    # If file does not exist we will write the header too
                    is_new_file = not os.path.isfile(KNOWN_DEVICES_FILE)

                    with open(KNOWN_DEVICES_FILE, 'a') as outp:
                        self.logger.info((
                            "DeviceTracker:Found {} new devices,"
                            " updating {}").format(len(unknown_devices),
                                                   KNOWN_DEVICES_FILE))

                        writer = csv.writer(outp)

                        if is_new_file:
                            writer.writerow(("device", "name", "track"))

                        for device in unknown_devices:
                            # See if the device scanner knows the name
                            temp_name = \
                                self.device_scanner.get_device_name(device)

                            name = temp_name if temp_name else "unknown_device"

                            writer.writerow((device, name, 0))
                            self.known_devices[device] = {'name': name,
                                                          'track': False}

                except IOError:
                    self.logger.exception((
                        "DeviceTracker:Error updating {}"
                        "with {} new devices").format(
                        KNOWN_DEVICES_FILE, len(unknown_devices)))

        self.lock.release()

    def _read_known_devices_file(self):
        """ Parse and process the known devices file. """

        # Read known devices if file exists
        if os.path.isfile(KNOWN_DEVICES_FILE):
            self.lock.acquire()

            known_devices = {}

            with open(KNOWN_DEVICES_FILE) as inp:
                default_last_seen = datetime(1990, 1, 1)

                # Temp variable to keep track of which categories we use
                # so we can ensure we have unique categories.
                used_categories = []

                try:
                    for row in csv.DictReader(inp):
                        device = row['device']

                        row['track'] = True if row['track'] == '1' else False

                        # If we track this device setup tracking variables
                        if row['track']:
                            row['last_seen'] = default_last_seen

                            # Make sure that each device is mapped
                            # to a unique category name
                            name = util.slugify(row['name']) if row['name'] \
                                else "unnamed_device"

                            tries = 0
                            suffix = ""
                            while True:
                                tries += 1

                                if tries > 1:
                                    suffix = "_{}".format(tries)

                                category = STATE_CATEGORY_FORMAT.format(
                                    name + suffix)

                                if category not in used_categories:
                                    break

                            row['category'] = category
                            used_categories.append(category)

                        known_devices[device] = row

                    if len(known_devices) == 0:
                        self.logger.warning(
                            "No devices to track. Please update {}.".format(
                                KNOWN_DEVICES_FILE))

                    # Remove categories that are no longer maintained
                    new_categories = set([known_devices[device]['category']
                                         for device in known_devices
                                         if known_devices[device]['track']])

                    for category in \
                            self.device_state_categories - new_categories:

                        print "Removing ", category
                        self.statemachine.remove_category(category)

                    # File parsed, warnings given if necessary
                    # categories cleaned up, make it available
                    self.known_devices = known_devices

                    self.logger.info(
                        "DeviceTracker:Loaded devices from {}".format(
                            KNOWN_DEVICES_FILE))

                except KeyError:
                    self.invalid_known_devices_file = True
                    self.logger.warning((
                        "Invalid {} found. "
                        "We won't update it with new found devices.").
                        format(KNOWN_DEVICES_FILE))

                finally:
                    self.lock.release()


class TomatoDeviceScanner(object):
    """ This class queries a wireless router running Tomato firmware
    for connected devices.

    A description of the Tomato API can be found on
    http://paulusschoutsen.nl/blog/2013/10/tomato-api-documentation/
    """

    def __init__(self, host, username, password, http_id):
        self.req = requests.Request('POST',
                                    'http://{}/update.cgi'.format(host),
                                    data={'_http_id': http_id,
                                          'exec': 'devlist'},
                                    auth=requests.auth.HTTPBasicAuth(
                                        username, password)).prepare()

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")

        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()

        self.date_updated = None
        self.last_results = {"wldev": [], "dhcpd_lease": []}

        self.success_init = self._update_tomato_info()

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_tomato_info()

        return [item[1] for item in self.last_results['wldev']]

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """

        # Make sure there are results
        if not self.date_updated:
            self._update_tomato_info()

        filter_named = [item[0] for item in self.last_results['dhcpd_lease']
                        if item[2] == device]

        if len(filter_named) == 0 or filter_named[0] == "":
            return None
        else:
            return filter_named[0]

    def _update_tomato_info(self):
        """ Ensures the information from the Tomato router is up to date.
            Returns boolean if scanning successful. """

        self.lock.acquire()

        # if date_updated is None or the date is too old we scan for new data
        if (not self.date_updated or datetime.now() - self.date_updated >
           MIN_TIME_BETWEEN_SCANS):

            self.logger.info("Tomato:Scanning")

            try:
                response = requests.Session().send(self.req, timeout=3)

                # Calling and parsing the Tomato api here. We only need the
                # wldev and dhcpd_lease values. For API description see:
                # http://paulusschoutsen.nl/
                #   blog/2013/10/tomato-api-documentation/
                if response.status_code == 200:

                    for param, value in \
                            self.parse_api_pattern.findall(response.text):

                        if param == 'wldev' or param == 'dhcpd_lease':
                            self.last_results[param] = \
                                json.loads(value.replace("'", '"'))

                    self.date_updated = datetime.now()

                    return True

                elif response.status_code == 401:
                    # Authentication error
                    self.logger.exception((
                        "Tomato:Failed to authenticate, "
                        "please check your username and password"))

                    return False

            except requests.exceptions.ConnectionError:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception((
                    "Tomato:Failed to connect to the router"
                    " or invalid http_id supplied"))

                return False

            except requests.exceptions.Timeout:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception(
                    "Tomato:Connection to the router timed out")

                return False

            except ValueError:
                # If json decoder could not parse the response
                self.logger.exception(
                    "Tomato:Failed to parse response from router")

                return False

            finally:
                self.lock.release()

        else:
            # We acquired the lock before the IF check,
            # release it before we return True
            self.lock.release()

            return True


class NetgearDeviceScanner(object):
    """ This class queries a Netgear wireless router.

    Tested with the Netgear R6300.
    """

    def __init__(self, host, username, password):
        self.req = requests.Request('GET',
                                    'http://{}/DEV_device.htm'.format(host),
                                    auth=requests.auth.HTTPBasicAuth(
                                        username, password)).prepare()

        self.req_main_page = requests.Request('GET',
                                    'http://{}/start.htm'.format(host),
                                    auth=requests.auth.HTTPBasicAuth(
                                        username, password)).prepare()


        self.parse_api_pattern = re.compile(r'ttext">(.*?)<')

        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()

        self.date_updated = None
        self.last_results = []

        self.success_init = self._update_info()

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_info()

        return [item[2] for item in self.last_results]

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """

        # Make sure there are results
        if not self.date_updated:
            self._update_info()

        filter_named = [item[1] for item in self.last_results
                        if item[2] == device]

        if len(filter_named) == 0 or filter_named[0] == "--":
            return None
        else:
            return filter_named[0]

    def _update_info(self):
        """ Retrieves latest information from the Netgear router.
            Returns boolean if scanning successful. """

        self.lock.acquire()

        # if date_updated is None or the date is too old we scan for new data
        if (not self.date_updated or datetime.now() - self.date_updated >
           MIN_TIME_BETWEEN_SCANS):

            self.logger.info("Netgear:Scanning")

            try:
                response = requests.Session().send(self.req, timeout=3)

                # Netgear likes us to hit the main page first
                # So first 401 we get we will first hit main page
                if response.status_code == 401:
                    response = requests.Session().send(self.req_main_page, timeout=3)
                    response = requests.Session().send(self.req, timeout=3)

                if response.status_code == 200:

                    entries = self.parse_api_pattern.findall(response.text)

                    if len(entries) % 3 != 0:
                        self.logger.error("Netgear:Failed to parse response")
                        return False

                    else:
                        self.last_results = [entries[i:i+3] for i
                                             in xrange(0, len(entries), 3)]

                        self.date_updated = datetime.now()

                        return True

                elif response.status_code == 401:
                    # Authentication error
                    self.logger.exception((
                        "Netgear:Failed to authenticate, "
                        "please check your username and password"))

                    return False

            except requests.exceptions.ConnectionError:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception((
                    "Netgear:Failed to connect to the router"
                    " or invalid http_id supplied"))

                return False

            except requests.exceptions.Timeout:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception(
                    "Netgear:Connection to the router timed out")

                return False

            finally:
                self.lock.release()

        else:
            # We acquired the lock before the IF check,
            # release it before we return True
            self.lock.release()

            return True
