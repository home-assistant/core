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
DEPENDENCIES = []

SERVICE_DEVICE_TRACKER_RELOAD = "reload_devices_csv"

GROUP_NAME_ALL_DEVICES = 'all_devices'
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

CONF_HTTP_ID = "http_id"

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Returns if any or specified device is home. """
    entity = entity_id or ENTITY_ID_ALL_DEVICES

    return hass.states.is_state(entity, components.STATE_HOME)


def setup(hass, config):
    """ Sets up the device tracker. """

    # We have flexible requirements for device tracker so
    # we cannot use util.validate_config

    conf = config[DOMAIN]

    if ha.CONF_TYPE not in conf:
        _LOGGER.error(
            'Missing required configuration item in %s: %s',
            DOMAIN, ha.CONF_TYPE)

        return False

    fields = [ha.CONF_HOST, ha.CONF_USERNAME, ha.CONF_PASSWORD]

    router_type = conf[ha.CONF_TYPE]

    if router_type == 'tomato':
        fields.append(CONF_HTTP_ID)

        scanner = TomatoDeviceScanner

    elif router_type == 'netgear':
        scanner = NetgearDeviceScanner

    elif router_type == 'luci':
        scanner = LuciDeviceScanner

    else:
        _LOGGER.error('Found unknown router type %s', router_type)

        return False

    if not util.validate_config(config, {DOMAIN: fields}, _LOGGER):
        return False

    device_scanner = scanner(conf)

    if not device_scanner.success_init:
        _LOGGER.error("Failed to initialize device scanner for %s",
                      router_type)

        return False

    DeviceTracker(hass, device_scanner)

    return True


# pylint: disable=too-many-instance-attributes
class DeviceTracker(object):
    """ Class that tracks which devices are home and which are not. """

    def __init__(self, hass, device_scanner):
        self.states = hass.states

        self.device_scanner = device_scanner

        self.error_scanning = TIME_SPAN_FOR_ERROR_IN_SCANNING

        self.lock = threading.Lock()

        self.path_known_devices_file = hass.get_config_path(KNOWN_DEVICES_FILE)

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

        hass.track_time_change(update_device_state)

        hass.services.register(DOMAIN,
                               SERVICE_DEVICE_TRACKER_RELOAD,
                               lambda service: self._read_known_devices_file())

        self.update_devices()

        group.setup_group(
            hass, GROUP_NAME_ALL_DEVICES, self.device_entity_ids, False)

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

                self.states.set(
                    known_dev[device]['entity_id'], components.STATE_HOME,
                    known_dev[device]['default_state_attr'])

        # For all devices we did not find, set state to NH
        # But only if they have been gone for longer then the error time span
        # Because we do not want to have stuff happening when the device does
        # not show up for 1 scan beacuse of reboot etc
        for device in temp_tracking_devices:
            if now - known_dev[device]['last_seen'] > self.error_scanning:

                self.states.set(known_dev[device]['entity_id'],
                                components.STATE_NOT_HOME,
                                known_dev[device]['default_state_attr'])

        # If we come along any unknown devices we will write them to the
        # known devices file but only if we did not encounter an invalid
        # known devices file
        if not self.invalid_known_devices_file:

            known_dev_path = self.path_known_devices_file

            unknown_devices = [device for device in found_devices
                               if device not in known_dev]

            if unknown_devices:
                try:
                    # If file does not exist we will write the header too
                    is_new_file = not os.path.isfile(known_dev_path)

                    with open(known_dev_path, 'a') as outp:
                        _LOGGER.info((
                            "Found {} new devices,"
                            " updating {}").format(len(unknown_devices),
                                                   known_dev_path))

                        writer = csv.writer(outp)

                        if is_new_file:
                            writer.writerow((
                                "device", "name", "track", "picture"))

                        for device in unknown_devices:
                            # See if the device scanner knows the name
                            # else defaults to unknown device
                            name = (self.device_scanner.get_device_name(device)
                                    or "unknown_device")

                            writer.writerow((device, name, 0, ""))
                            known_dev[device] = {'name': name,
                                                 'track': False,
                                                 'picture': ""}

                except IOError:
                    _LOGGER.exception((
                        "Error updating {}"
                        "with {} new devices").format(known_dev_path,
                                                      len(unknown_devices)))

        self.lock.release()

    def _read_known_devices_file(self):
        """ Parse and process the known devices file. """

        # Read known devices if file exists
        if os.path.isfile(self.path_known_devices_file):
            self.lock.acquire()

            known_devices = {}

            with open(self.path_known_devices_file) as inp:
                default_last_seen = datetime(1990, 1, 1)

                # Temp variable to keep track of which entity ids we use
                # so we can ensure we have unique entity ids.
                used_entity_ids = []

                try:
                    for row in csv.DictReader(inp):
                        device = row['device']

                        row['track'] = True if row['track'] == '1' else False

                        if row['picture']:
                            row['default_state_attr'] = {
                                components.ATTR_ENTITY_PICTURE: row['picture']}

                        else:
                            row['default_state_attr'] = None

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

                            row['picture'] = row['picture']

                        known_devices[device] = row

                    if not known_devices:
                        _LOGGER.warning(
                            "No devices to track. Please update %s.",
                            self.path_known_devices_file)

                    # Remove entities that are no longer maintained
                    new_entity_ids = set([known_devices[device]['entity_id']
                                          for device in known_devices
                                          if known_devices[device]['track']])

                    for entity_id in \
                            self.device_entity_ids - new_entity_ids:

                        _LOGGER.info("Removing entity %s", entity_id)
                        self.states.remove(entity_id)

                    # File parsed, warnings given if necessary
                    # entities cleaned up, make it available
                    self.known_devices = known_devices

                    _LOGGER.info("Loaded devices from %s",
                                 self.path_known_devices_file)

                except KeyError:
                    self.invalid_known_devices_file = True
                    _LOGGER.warning(
                        ("Invalid known devices file: %s. "
                         "We won't update it with new found devices."),
                        self.path_known_devices_file)

                finally:
                    self.lock.release()


class TomatoDeviceScanner(object):
    """ This class queries a wireless router running Tomato firmware
    for connected devices.

    A description of the Tomato API can be found on
    http://paulusschoutsen.nl/blog/2013/10/tomato-api-documentation/
    """

    def __init__(self, config):
        host, http_id = config['host'], config['http_id']
        username, password = config['username'], config['password']

        self.req = requests.Request('POST',
                                    'http://{}/update.cgi'.format(host),
                                    data={'_http_id': http_id,
                                          'exec': 'devlist'},
                                    auth=requests.auth.HTTPBasicAuth(
                                        username, password)).prepare()

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")

        self.logger = logging.getLogger("{}.{}".format(__name__, "Tomato"))
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
        if not self.date_updated or \
           datetime.now() - self.date_updated > MIN_TIME_BETWEEN_SCANS:

            self.logger.info("Scanning")

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
                        "Failed to authenticate, "
                        "please check your username and password"))

                    return False

            except requests.exceptions.ConnectionError:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception((
                    "Failed to connect to the router"
                    " or invalid http_id supplied"))

                return False

            except requests.exceptions.Timeout:
                # We get this if we could not connect to the router or
                # an invalid http_id was supplied
                self.logger.exception(
                    "Connection to the router timed out")

                return False

            except ValueError:
                # If json decoder could not parse the response
                self.logger.exception(
                    "Failed to parse response from router")

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

    def __init__(self, config):
        host = config['host']
        username, password = config['username'], config['password']

        self.logger = logging.getLogger("{}.{}".format(__name__, "Netgear"))
        self.date_updated = None
        self.last_results = []

        try:
            # Pylint does not play nice if not every folders has an __init__.py
            # pylint: disable=no-name-in-module, import-error
            import homeassistant.external.pynetgear.pynetgear as pynetgear
        except ImportError:
            self.logger.exception(
                ("Failed to import pynetgear. "
                 "Did you maybe not run `git submodule init` "
                 "and `git submodule update`?"))

            self.success_init = False

            return

        self._api = pynetgear.Netgear(host, username, password)
        self.lock = threading.Lock()

        self.logger.info("Logging in")
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
            if not self.date_updated or \
               datetime.now() - self.date_updated > MIN_TIME_BETWEEN_SCANS:

                self.logger.info("Scanning")

                self.last_results = self._api.get_attached_devices()

                self.date_updated = datetime.now()

                return

            else:
                return


class LuciDeviceScanner(object):
    """ This class queries a wireless router running OpenWrt firmware
    for connected devices. Adapted from Tomato scanner.

    # opkg install luci-mod-rpc
    for this to work on the router.

    The API is described here:
    http://luci.subsignal.org/trac/wiki/Documentation/JsonRpcHowTo

    (Currently, we do only wifi iwscan, and no DHCP lease access.)
    """

    def __init__(self, config):
        host = config['host']
        username, password = config['username'], config['password']

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")

        self.logger = logging.getLogger("{}.{}".format(__name__, "Luci"))
        self.lock = threading.Lock()

        self.date_updated = None
        self.last_results = {}

        self.token = self.get_token(host, username, password)
        self.host = host

        self.mac2name = None
        self.success_init = self.token

    def _req_json_rpc(self, url, method, *args, **kwargs):
        """ Perform one JSON RPC operation. """
        data = json.dumps({'method': method, 'params': args})
        try:
            res = requests.post(url, data=data, timeout=5, **kwargs)
        except requests.exceptions.Timeout:
            self.logger.exception("Connection to the router timed out")
            return
        if res.status_code == 200:
            try:
                result = res.json()
            except ValueError:
                # If json decoder could not parse the response
                self.logger.exception("Failed to parse response from luci")
                return
            try:
                return result['result']
            except KeyError:
                self.logger.exception("No result in response from luci")
                return
        elif res.status_code == 401:
            # Authentication error
            self.logger.exception(
                "Failed to authenticate, "
                "please check your username and password")
            return
        else:
            self.logger.error("Invalid response from luci: %s", res)

    def get_token(self, host, username, password):
        """ Get authentication token for the given host+username+password """
        url = 'http://{}/cgi-bin/luci/rpc/auth'.format(host)
        return self._req_json_rpc(url, 'login', username, password)

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_info()

        return self.last_results

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """

        with self.lock:
            if self.mac2name is None:
                url = 'http://{}/cgi-bin/luci/rpc/uci'.format(self.host)
                result = self._req_json_rpc(url, 'get_all', 'dhcp',
                                            params={'auth': self.token})
                if result:
                    hosts = [x for x in result.values()
                             if x['.type'] == 'host' and
                             'mac' in x and 'name' in x]
                    mac2name_list = [(x['mac'], x['name']) for x in hosts]
                    self.mac2name = dict(mac2name_list)
                else:
                    # Error, handled in the _req_json_rpc
                    return
            return self.mac2name.get(device, None)

    def _update_info(self):
        """ Ensures the information from the Luci router is up to date.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return False
        with self.lock:
            # if date_updated is None or the date is too old we scan
            # for new data
            if not self.date_updated or \
               datetime.now() - self.date_updated > MIN_TIME_BETWEEN_SCANS:

                self.logger.info("Checking ARP")

                url = 'http://{}/cgi-bin/luci/rpc/sys'.format(self.host)
                result = self._req_json_rpc(url, 'net.arptable',
                                            params={'auth': self.token})
                if result:
                    self.last_results = [x['HW address'] for x in result]
                    self.date_updated = datetime.now()
                    return True
                return False

            return True
