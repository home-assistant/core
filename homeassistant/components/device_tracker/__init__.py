"""
homeassistant.components.tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to keep track of devices.
"""
import logging
import threading
import os
import csv
from datetime import timedelta

from homeassistant.loader import get_component
from homeassistant.helpers import validate_config
import homeassistant.util as util
import homeassistant.util.dt as dt_util

from homeassistant.helpers.event import track_utc_time_change
from homeassistant.const import (
    STATE_HOME, STATE_NOT_HOME, ATTR_ENTITY_PICTURE, ATTR_FRIENDLY_NAME,
    CONF_PLATFORM, DEVICE_DEFAULT_NAME)
from homeassistant.components import group

DOMAIN = "device_tracker"
DEPENDENCIES = []

SERVICE_DEVICE_TRACKER_RELOAD = "reload_devices_csv"

GROUP_NAME_ALL_DEVICES = 'all devices'
ENTITY_ID_ALL_DEVICES = group.ENTITY_ID_FORMAT.format('all_devices')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# After how much time do we consider a device not home if
# it does not show up on scans
TIME_DEVICE_NOT_FOUND = timedelta(minutes=3)

# Filename to save known devices to
KNOWN_DEVICES_FILE = "known_devices.csv"

CONF_SECONDS = "interval_seconds"

DEFAULT_CONF_SECONDS = 12

TRACK_NEW_DEVICES = "track_new_devices"

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Returns if any or specified device is home. """
    entity = entity_id or ENTITY_ID_ALL_DEVICES

    return hass.states.is_state(entity, STATE_HOME)


def setup(hass, config):
    """ Sets up the device tracker. """

    if not validate_config(config, {DOMAIN: [CONF_PLATFORM]}, _LOGGER):
        return False

    tracker_type = config[DOMAIN].get(CONF_PLATFORM)

    tracker_implementation = get_component(
        'device_tracker.{}'.format(tracker_type))

    if tracker_implementation is None:
        _LOGGER.error("Unknown device_tracker type specified: %s.",
                      tracker_type)

        return False

    device_scanner = tracker_implementation.get_scanner(hass, config)

    if device_scanner is None:
        _LOGGER.error("Failed to initialize device scanner: %s",
                      tracker_type)

        return False

    seconds = util.convert(config[DOMAIN].get(CONF_SECONDS), int,
                           DEFAULT_CONF_SECONDS)

    track_new_devices = config[DOMAIN].get(TRACK_NEW_DEVICES) or False
    _LOGGER.info("Tracking new devices: %s", track_new_devices)

    tracker = DeviceTracker(hass, device_scanner, seconds, track_new_devices)

    # We only succeeded if we got to parse the known devices file
    return not tracker.invalid_known_devices_file


class DeviceTracker(object):
    """ Class that tracks which devices are home and which are not. """

    def __init__(self, hass, device_scanner, seconds, track_new_devices):
        self.hass = hass

        self.device_scanner = device_scanner

        self.lock = threading.Lock()

        # Do we track new devices by default?
        self.track_new_devices = track_new_devices

        # Dictionary to keep track of known devices and devices we track
        self.tracked = {}
        self.untracked_devices = set()

        # Did we encounter an invalid known devices file
        self.invalid_known_devices_file = False

        # Wrap it in a func instead of lambda so it can be identified in
        # the bus by its __name__ attribute.
        def update_device_state(now):
            """ Triggers update of the device states. """
            self.update_devices(now)

        dev_group = group.Group(
            hass, GROUP_NAME_ALL_DEVICES, user_defined=False)

        def reload_known_devices_service(service):
            """ Reload known devices file. """
            self._read_known_devices_file()

            self.update_devices(dt_util.utcnow())

            dev_group.update_tracked_entity_ids(self.device_entity_ids)

        reload_known_devices_service(None)

        if self.invalid_known_devices_file:
            return

        seconds = range(0, 60, seconds)

        _LOGGER.info("Device tracker interval second=%s", seconds)
        track_utc_time_change(hass, update_device_state, second=seconds)

        hass.services.register(DOMAIN,
                               SERVICE_DEVICE_TRACKER_RELOAD,
                               reload_known_devices_service)

    @property
    def device_entity_ids(self):
        """ Returns a set containing all device entity ids
            that are being tracked. """
        return set(device['entity_id'] for device in self.tracked.values())

    def _update_state(self, now, device, is_home):
        """ Update the state of a device. """
        dev_info = self.tracked[device]

        if is_home:
            # Update last seen if at home
            dev_info['last_seen'] = now
        else:
            # State remains at home if it has been seen in the last
            # TIME_DEVICE_NOT_FOUND
            is_home = now - dev_info['last_seen'] < TIME_DEVICE_NOT_FOUND

        state = STATE_HOME if is_home else STATE_NOT_HOME

        self.hass.states.set(
            dev_info['entity_id'], state,
            dev_info['state_attr'])

    def update_devices(self, now):
        """ Update device states based on the found devices. """
        if not self.lock.acquire(False):
            return

        try:
            found_devices = set(dev.upper() for dev in
                                self.device_scanner.scan_devices())

            for device in self.tracked:
                is_home = device in found_devices

                self._update_state(now, device, is_home)

                if is_home:
                    found_devices.remove(device)

            # Did we find any devices that we didn't know about yet?
            new_devices = found_devices - self.untracked_devices

            if new_devices:
                if not self.track_new_devices:
                    self.untracked_devices.update(new_devices)

                self._update_known_devices_file(new_devices)
        finally:
            self.lock.release()

    # pylint: disable=too-many-branches
    def _read_known_devices_file(self):
        """ Parse and process the known devices file. """
        known_dev_path = self.hass.config.path(KNOWN_DEVICES_FILE)

        # Return if no known devices file exists
        if not os.path.isfile(known_dev_path):
            return

        self.lock.acquire()

        self.untracked_devices.clear()

        with open(known_dev_path) as inp:

            # To track which devices need an entity_id assigned
            need_entity_id = []

            # All devices that are still in this set after we read the CSV file
            # have been removed from the file and thus need to be cleaned up.
            removed_devices = set(self.tracked.keys())

            try:
                for row in csv.DictReader(inp):
                    device = row['device'].upper()

                    if row['track'] == '1':
                        if device in self.tracked:
                            # Device exists
                            removed_devices.remove(device)
                        else:
                            # We found a new device
                            need_entity_id.append(device)

                            self._track_device(device, row['name'])

                        # Update state_attr with latest from file
                        state_attr = {
                            ATTR_FRIENDLY_NAME: row['name']
                        }

                        if row['picture']:
                            state_attr[ATTR_ENTITY_PICTURE] = row['picture']

                        self.tracked[device]['state_attr'] = state_attr

                    else:
                        self.untracked_devices.add(device)

                # Remove existing devices that we no longer track
                for device in removed_devices:
                    entity_id = self.tracked[device]['entity_id']

                    _LOGGER.info("Removing entity %s", entity_id)

                    self.hass.states.remove(entity_id)

                    self.tracked.pop(device)

                self._generate_entity_ids(need_entity_id)

                if not self.tracked:
                    _LOGGER.warning(
                        "No devices to track. Please update %s.",
                        known_dev_path)

                _LOGGER.info("Loaded devices from %s", known_dev_path)

            except KeyError:
                self.invalid_known_devices_file = True

                _LOGGER.warning(
                    ("Invalid known devices file: %s. "
                     "We won't update it with new found devices."),
                    known_dev_path)

            finally:
                self.lock.release()

    def _update_known_devices_file(self, new_devices):
        """ Add new devices to known devices file. """
        if not self.invalid_known_devices_file:
            known_dev_path = self.hass.config.path(KNOWN_DEVICES_FILE)

            try:
                # If file does not exist we will write the header too
                is_new_file = not os.path.isfile(known_dev_path)

                with open(known_dev_path, 'a') as outp:
                    _LOGGER.info("Found %d new devices, updating %s",
                                 len(new_devices), known_dev_path)

                    writer = csv.writer(outp)

                    if is_new_file:
                        writer.writerow(("device", "name", "track", "picture"))

                    for device in new_devices:
                        # See if the device scanner knows the name
                        # else defaults to unknown device
                        name = self.device_scanner.get_device_name(device) or \
                            DEVICE_DEFAULT_NAME

                        track = 0
                        if self.track_new_devices:
                            self._track_device(device, name)
                            track = 1

                        writer.writerow((device, name, track, ""))

                if self.track_new_devices:
                    self._generate_entity_ids(new_devices)

            except IOError:
                _LOGGER.exception("Error updating %s with %d new devices",
                                  known_dev_path, len(new_devices))

    def _track_device(self, device, name):
        """
        Add a device to the list of tracked devices.
        Does not generate the entity id yet.
        """
        default_last_seen = dt_util.utcnow().replace(year=1990)

        self.tracked[device] = {
            'name': name,
            'last_seen': default_last_seen,
            'state_attr': {ATTR_FRIENDLY_NAME: name}
        }

    def _generate_entity_ids(self, need_entity_id):
        """ Generate entity ids for a list of devices. """
        # Setup entity_ids for the new devices
        used_entity_ids = [info['entity_id'] for device, info
                           in self.tracked.items()
                           if device not in need_entity_id]

        for device in need_entity_id:
            name = self.tracked[device]['name']

            entity_id = util.ensure_unique_string(
                ENTITY_ID_FORMAT.format(util.slugify(name)),
                used_entity_ids)

            used_entity_ids.append(entity_id)

            self.tracked[device]['entity_id'] = entity_id
