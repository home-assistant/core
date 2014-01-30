"""
homeassistant.components.tracker
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
import homeassistant.components as components

from homeassistant.components import group

DOMAIN = "device_tracker"

SERVICE_DEVICE_TRACKER_RELOAD = "reload_devices_csv"

GROUP_NAME_ALL_DEVICES = 'all_tracked_devices'
ENTITY_ID_ALL_DEVICES = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_DEVICES)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# After how much time do we consider a device not home if
# it does not show up on scans
TIME_SPAN_FOR_ERROR_IN_SCANNING = timedelta(minutes=3)

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

# Filename to save known devices to
KNOWN_DEVICES_FILE = "known_devices.csv"


def is_on(statemachine, entity_id=None):
    """ Returns if any or specified device is home. """
    entity = entity_id or ENTITY_ID_ALL_DEVICES

    return statemachine.is_state(entity, components.STATE_HOME)


# pylint: disable=too-many-instance-attributes
class DeviceTracker(object):
    """ Class that tracks which devices are home and which are not. """

    def __init__(self, bus, statemachine, device_scanner, error_scanning=None):
        self.statemachine = statemachine
        self.bus = bus
        self.device_scanner = device_scanner

        self.error_scanning = error_scanning or TIME_SPAN_FOR_ERROR_IN_SCANNING

        self.logger = logging.getLogger(__name__)

        self.lock = threading.Lock()

        # Dictionary to keep track of known devices and devices we track
        self.known_devices = {}

        # Did we encounter an invalid known devices file
        self.invalid_known_devices_file = False

        self._read_known_devices_file()

        # Wrap it in a func instead of lambda so it can be identified in
        # the bus by its __name__ attribute.
        def update_device_state(time):  # pylint: disable=unused-argument
            """ Triggers update of the device states. """
            self.update_devices()

        ha.track_time_change(bus, update_device_state)

        bus.register_service(DOMAIN,
                             SERVICE_DEVICE_TRACKER_RELOAD,
                             lambda service: self._read_known_devices_file())

        self.update_devices()

        group.setup(bus, statemachine, GROUP_NAME_ALL_DEVICES,
                    list(self.device_entity_ids))

    @property
    def device_entity_ids(self):
        """ Returns a set containing all device entity ids
            that are being tracked. """
        return set([self.known_devices[device]['entity_id'] for device
                    in self.known_devices
                    if self.known_devices[device]['track']])

    def update_devices(self, found_devices=None):
        """ Update device states based on the found devices. """
        self.lock.acquire()

        found_devices = found_devices or self.device_scanner.scan_devices()

        now = datetime.now()

        known_dev = self.known_devices

        temp_tracking_devices = [device for device in known_dev
                                 if known_dev[device]['track']]

        for device in found_devices:
            # Are we tracking this device?
            if device in temp_tracking_devices:
                temp_tracking_devices.remove(device)

                known_dev[device]['last_seen'] = now

                self.statemachine.set_state(
                    known_dev[device]['entity_id'], components.STATE_HOME)

        # For all devices we did not find, set state to NH
        # But only if they have been gone for longer then the error time span
        # Because we do not want to have stuff happening when the device does
        # not show up for 1 scan beacuse of reboot etc
        for device in temp_tracking_devices:
            if (now - known_dev[device]['last_seen'] > self.error_scanning):

                self.statemachine.set_state(known_dev[device]['entity_id'],
                                            components.STATE_NOT_HOME)

        # If we come along any unknown devices we will write them to the
        # known devices file but only if we did not encounter an invalid
        # known devices file
        if not self.invalid_known_devices_file:

            unknown_devices = [device for device in found_devices
                               if device not in known_dev]

            if unknown_devices:
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
                            # else defaults to unknown device
                            name = (self.device_scanner.get_device_name(device)
                                    or "unknown_device")

                            writer.writerow((device, name, 0))
                            known_dev[device] = {'name': name,
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

                # Temp variable to keep track of which entity ids we use
                # so we can ensure we have unique entity ids.
                used_entity_ids = []

                try:
                    for row in csv.DictReader(inp):
                        device = row['device']

                        row['track'] = True if row['track'] == '1' else False

                        # If we track this device setup tracking variables
                        if row['track']:
                            row['last_seen'] = default_last_seen

                            # Make sure that each device is mapped
                            # to a unique entity_id name
                            name = util.slugify(row['name']) if row['name'] \
                                else "unnamed_device"

                            entity_id = ENTITY_ID_FORMAT.format(name)
                            tries = 1

                            while entity_id in used_entity_ids:
                                tries += 1

                                suffix = "_{}".format(tries)

                                entity_id = ENTITY_ID_FORMAT.format(
                                    name + suffix)

                            row['entity_id'] = entity_id
                            used_entity_ids.append(entity_id)

                        known_devices[device] = row

                    if not known_devices:
                        self.logger.warning(
                            "No devices to track. Please update {}.".format(
                                KNOWN_DEVICES_FILE))

                    # Remove entities that are no longer maintained
                    new_entity_ids = set([known_devices[device]['entity_id']
                                         for device in known_devices
                                         if known_devices[device]['track']])

                    for entity_id in \
                            self.device_entity_ids - new_entity_ids:

                        self.logger.info(
                            "DeviceTracker:Removing entity {}".format(
                                entity_id))
                        self.statemachine.remove_entity(entity_id)

                    # File parsed, warnings given if necessary
                    # entities cleaned up, make it available
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

        if not filter_named or not filter_named[0]:
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
    """ This class queries a Netgear wireless router using the SOAP-api. """

    def __init__(self, host, username, password):
        self.logger = logging.getLogger(__name__)
        self.date_updated = None
        self.last_results = []

        try:
            import homeassistant.external.pynetgear as pynetgear
        except ImportError:
            self.logger.exception(
                ("Netgear:Failed to import pynetgear. "
                 "Did you maybe not cloned the git submodules?"))

            self.success_init = False

            return

        self._api = pynetgear.Netgear(host, username, password)
        self.lock = threading.Lock()

        self.logger.info("Netgear:Logging in")
        if self._api.login():
            self.success_init = True
            self._update_info()

        else:
            self.logger.error("Netgear:Failed to Login")

            self.success_init = False

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know. """

        # Make sure there are results
        if not self.date_updated:
            self._update_info()

        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]

        if filter_named:
            return filter_named[0]
        else:
            return None

    def _update_info(self):
        """ Retrieves latest information from the Netgear router.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return

        with self.lock:
            # if date_updated is None or the date is too old we scan for
            # new data
            if (not self.date_updated or datetime.now() - self.date_updated >
               MIN_TIME_BETWEEN_SCANS):

                self.logger.info("Netgear:Scanning")

                self.last_results = self._api.get_attached_devices()

                self.date_updated = datetime.now()

                return

            else:
                return
