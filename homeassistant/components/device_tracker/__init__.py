"""
homeassistant.components.tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to keep track of devices.
"""
import logging
import threading
import os
import csv
from datetime import datetime, timedelta

import homeassistant as ha
from homeassistant.loader import get_component
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

# Filename to save known devices to
KNOWN_DEVICES_FILE = "known_devices.csv"


_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """ Returns if any or specified device is home. """
    entity = entity_id or ENTITY_ID_ALL_DEVICES

    return hass.states.is_state(entity, components.STATE_HOME)


def setup(hass, config):
    """ Sets up the device tracker. """

    if not util.validate_config(config, {DOMAIN: [ha.CONF_TYPE]}, _LOGGER):
        return False

    tracker_type = config[DOMAIN][ha.CONF_TYPE]

    tracker_implementation = get_component(
        'device_tracker.{}'.format(tracker_type))

    if tracker_implementation is None:
        _LOGGER.error("Unknown device_tracker type specified.")

        return False

    device_scanner = tracker_implementation.get_scanner(hass, config)

    if device_scanner is None:
        _LOGGER.error("Failed to initialize device scanner for %s",
                      tracker_type)

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
                    new_entity_ids = set([known_devices[dev]['entity_id']
                                          for dev in known_devices
                                          if known_devices[dev]['track']])

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
