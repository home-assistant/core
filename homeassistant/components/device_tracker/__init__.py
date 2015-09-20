"""
homeassistant.components.device_tracker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to keep track of devices.

device_tracker:
  platform: netgear

  # Optional

  # How many seconds to wait after not seeing device to consider it not home
  consider_home: 180

  # Seconds between each scan
  interval_seconds: 12

  # New found devices auto found
  track_new_devices: yes
"""
import csv
from datetime import timedelta
import logging
import os
import threading

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.components import discovery, group
from homeassistant.config import load_yaml_config_file
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.entity import Entity
import homeassistant.util as util
import homeassistant.util.dt as dt_util

from homeassistant.helpers.event import track_utc_time_change
from homeassistant.const import (
    ATTR_ENTITY_PICTURE, DEVICE_DEFAULT_NAME, STATE_HOME, STATE_NOT_HOME)

DOMAIN = "device_tracker"
DEPENDENCIES = []

GROUP_NAME_ALL_DEVICES = 'all devices'
ENTITY_ID_ALL_DEVICES = group.ENTITY_ID_FORMAT.format('all_devices')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

CSV_DEVICES = "known_devices.csv"
YAML_DEVICES = 'known_devices.yaml'

CONF_TRACK_NEW = "track_new_devices"
DEFAULT_CONF_TRACK_NEW = True

CONF_CONSIDER_HOME = 'consider_home'
DEFAULT_CONF_CONSIDER_HOME = 180  # seconds

CONF_SCAN_INTERVAL = "interval_seconds"
DEFAULT_SCAN_INTERVAL = 12

CONF_AWAY_HIDE = 'hide_if_away'
DEFAULT_AWAY_HIDE = False

SERVICE_SEE = 'see'

ATTR_LATITUDE = 'latitude'
ATTR_LONGITUDE = 'longitude'
ATTR_MAC = 'mac'
ATTR_DEV_ID = 'dev_id'
ATTR_HOST_NAME = 'host_name'
ATTR_LOCATION_NAME = 'location_name'
ATTR_GPS = 'gps'

DISCOVERY_PLATFORMS = {
    discovery.SERVICE_NETGEAR: 'netgear',
}
_LOGGER = logging.getLogger(__name__)

# pylint: disable=too-many-arguments


def is_on(hass, entity_id=None):
    """ Returns if any or specified device is home. """
    entity = entity_id or ENTITY_ID_ALL_DEVICES

    return hass.states.is_state(entity, STATE_HOME)


def see(hass, mac=None, dev_id=None, host_name=None, location_name=None,
        gps=None):
    """ Call service to notify you see device. """
    data = {key: value for key, value in
            ((ATTR_MAC, mac),
             (ATTR_DEV_ID, dev_id),
             (ATTR_HOST_NAME, host_name),
             (ATTR_LOCATION_NAME, location_name),
             (ATTR_GPS, gps)) if value is not None}
    hass.services.call(DOMAIN, SERVICE_SEE, data)


def setup(hass, config):
    """ Setup device tracker """
    yaml_path = hass.config.path(YAML_DEVICES)
    csv_path = hass.config.path(CSV_DEVICES)
    if os.path.isfile(csv_path) and not os.path.isfile(yaml_path) and \
       convert_csv_config(csv_path, yaml_path):
        os.remove(csv_path)

    conf = config.get(DOMAIN, {})
    consider_home = util.convert(conf.get(CONF_CONSIDER_HOME), int,
                                 DEFAULT_CONF_CONSIDER_HOME)
    track_new = util.convert(conf.get(CONF_TRACK_NEW), bool,
                             DEFAULT_CONF_TRACK_NEW)

    devices = load_config(yaml_path, hass, timedelta(seconds=consider_home))
    tracker = DeviceTracker(hass, consider_home, track_new, devices)

    def setup_platform(p_type, p_config, disc_info=None):
        """ Setup a device tracker platform. """
        platform = prepare_setup_platform(hass, config, DOMAIN, p_type)
        if platform is None:
            return

        try:
            if hasattr(platform, 'get_scanner'):
                scanner = platform.get_scanner(hass, {DOMAIN: p_config})

                if scanner is None:
                    _LOGGER.error('Error setting up platform %s', p_type)
                    return

                setup_scanner_platform(hass, p_config, scanner, tracker.see)
                return

            if not platform.setup_scanner(hass, p_config, tracker.see):
                _LOGGER.error('Error setting up platform %s', p_type)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up platform %s', p_type)

    for p_type, p_config in \
            config_per_platform(config, DOMAIN, _LOGGER):
        setup_platform(p_type, p_config)

    def device_tracker_discovered(service, info):
        """ Called when a device tracker platform is discovered. """
        setup_platform(DISCOVERY_PLATFORMS[service], {}, info)

    discovery.listen(hass, DISCOVERY_PLATFORMS.keys(),
                     device_tracker_discovered)

    def update_stale(now):
        """ Clean up stale devices. """
        tracker.update_stale(now)
    track_utc_time_change(hass, update_stale, second=range(0, 60, 5))

    tracker.setup_group()

    def see_service(call):
        """ Service to see a device. """
        args = {key: value for key, value in call.data.items() if key in
                (ATTR_MAC, ATTR_DEV_ID, ATTR_HOST_NAME, ATTR_LOCATION_NAME,
                 ATTR_GPS)}
        tracker.see(**args)

    hass.services.register(DOMAIN, SERVICE_SEE, see_service)

    return True


class DeviceTracker(object):
    """ Track devices """
    def __init__(self, hass, consider_home, track_new, devices):
        self.hass = hass
        self.devices = {dev.dev_id: dev for dev in devices}
        self.mac_to_dev = {dev.mac: dev for dev in devices if dev.mac}
        self.consider_home = timedelta(seconds=consider_home)
        self.track_new = track_new
        self.lock = threading.Lock()

        for device in devices:
            if device.track:
                device.update_ha_state()

        self.group = None

    def see(self, mac=None, dev_id=None, host_name=None, location_name=None,
            gps=None):
        """ Notify device tracker that you see a device. """
        with self.lock:
            if mac is None and dev_id is None:
                raise HomeAssistantError('Neither mac or device id passed in')
            elif mac is not None:
                mac = mac.upper()
                device = self.mac_to_dev.get(mac)
                if not device:
                    dev_id = util.slugify(host_name or '') or util.slugify(mac)
            else:
                dev_id = str(dev_id).lower()
                device = self.devices.get(dev_id)

            if device:
                device.seen(host_name, location_name, gps)
                if device.track:
                    device.update_ha_state()
                return

            # If no device can be found, create it
            device = Device(
                self.hass, self.consider_home, self.track_new, dev_id, mac,
                (host_name or dev_id).replace('_', ' '))
            self.devices[dev_id] = device
            if mac is not None:
                self.mac_to_dev[mac] = device

            device.seen(host_name, location_name, gps)
            if device.track:
                device.update_ha_state()

            # During init, we ignore the group
            if self.group is not None:
                self.group.update_tracked_entity_ids(
                    list(self.group.tracking) + [device.entity_id])
            update_config(self.hass.config.path(YAML_DEVICES), dev_id, device)

    def setup_group(self):
        """ Initializes group for all tracked devices. """
        entity_ids = (dev.entity_id for dev in self.devices.values()
                      if dev.track)
        self.group = group.setup_group(
            self.hass, GROUP_NAME_ALL_DEVICES, entity_ids, False)

    def update_stale(self, now):
        """ Update stale devices. """
        with self.lock:
            for device in self.devices.values():
                if (device.track and device.last_update_home and
                        device.stale(now)):
                    device.update_ha_state(True)


class Device(Entity):
    """ Tracked device. """
    # pylint: disable=too-many-instance-attributes, too-many-arguments

    host_name = None
    location_name = None
    gps = None
    last_seen = None

    # Track if the last update of this device was HOME
    last_update_home = False
    _state = STATE_NOT_HOME

    def __init__(self, hass, consider_home, track, dev_id, mac, name=None,
                 picture=None, away_hide=False):
        self.hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(dev_id)

        # Timedelta object how long we consider a device home if it is not
        # detected anymore.
        self.consider_home = consider_home

        # Device ID
        self.dev_id = dev_id
        self.mac = mac

        # If we should track this device
        self.track = track

        # Configured name
        self.config_name = name

        # Configured picture
        self.config_picture = picture
        self.away_hide = away_hide

    @property
    def name(self):
        """ Returns the name of the entity. """
        return self.config_name or self.host_name or DEVICE_DEFAULT_NAME

    @property
    def state(self):
        """ State of the device. """
        return self._state

    @property
    def state_attributes(self):
        """ Device state attributes. """
        attr = {}

        if self.config_picture:
            attr[ATTR_ENTITY_PICTURE] = self.config_picture

        if self.gps:
            attr[ATTR_LATITUDE] = self.gps[0],
            attr[ATTR_LONGITUDE] = self.gps[1],

        return attr

    @property
    def hidden(self):
        """ If device should be hidden. """
        return self.away_hide and self.state != STATE_HOME

    def seen(self, host_name=None, location_name=None, gps=None):
        """ Mark the device as seen. """
        self.last_seen = dt_util.utcnow()
        self.host_name = host_name
        self.location_name = location_name
        self.gps = gps
        self.update()

    def stale(self, now=None):
        """ Return if device state is stale. """
        return self.last_seen and \
            (now or dt_util.utcnow()) - self.last_seen > self.consider_home

    def update(self):
        """ Update state of entity. """
        if not self.last_seen:
            return
        elif self.location_name:
            self._state = self.location_name
        elif self.stale():
            self._state = STATE_NOT_HOME
            self.last_update_home = False
        else:
            self._state = STATE_HOME
            self.last_update_home = True


def convert_csv_config(csv_path, yaml_path):
    """ Convert CSV config file format to YAML. """
    used_ids = set()
    with open(csv_path) as inp:
        for row in csv.DictReader(inp):
            dev_id = util.ensure_unique_string(
                (util.slugify(row['name']) or DEVICE_DEFAULT_NAME).lower(),
                used_ids)
            used_ids.add(dev_id)
            device = Device(None, None, row['track'] == '1', dev_id,
                            row['device'], row['name'], row['picture'])
            update_config(yaml_path, dev_id, device)
    return True


def load_config(path, hass, consider_home):
    """ Load devices from YAML config file. """
    if not os.path.isfile(path):
        return []
    return [
        Device(hass, consider_home, device.get('track', False),
               str(dev_id).lower(), str(device.get('mac')).upper(),
               device.get('name'), device.get('picture'),
               device.get(CONF_AWAY_HIDE, DEFAULT_AWAY_HIDE))
        for dev_id, device in load_yaml_config_file(path).items()]


def setup_scanner_platform(hass, config, scanner, see_device):
    """ Helper method to connect scanner-based platform to device tracker. """
    interval = util.convert(config.get(CONF_SCAN_INTERVAL), int,
                            DEFAULT_SCAN_INTERVAL)

    # Initial scan of each mac we also tell about host name for config
    seen = set()

    def device_tracker_scan(now):
        """ Called when interval matches. """
        for mac in scanner.scan_devices():
            if mac in seen:
                host_name = None
            else:
                host_name = scanner.get_device_name(mac)
                seen.add(mac)
            see_device(mac=mac, host_name=host_name)

    track_utc_time_change(hass, device_tracker_scan, second=range(0, 60,
                                                                  interval))

    device_tracker_scan(None)


def update_config(path, dev_id, device):
    """ Add device to YAML config file. """
    with open(path, 'a') as out:
        out.write('\n')
        out.write('{}:\n'.format(device.dev_id))

        for key, value in (('name', device.name), ('mac', device.mac),
                           ('picture', device.config_picture),
                           ('track', 'yes' if device.track else 'no'),
                           (CONF_AWAY_HIDE,
                            'yes' if device.away_hide else 'no')):
            out.write('  {}: {}\n'.format(key, '' if value is None else value))
