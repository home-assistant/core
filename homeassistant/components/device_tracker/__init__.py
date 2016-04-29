"""
Provide functionality to keep track of devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/device_tracker/
"""
# pylint: disable=too-many-instance-attributes, too-many-arguments
# pylint: disable=too-many-locals
from datetime import timedelta
import logging
import os
import threading

from homeassistant.bootstrap import prepare_setup_platform
from homeassistant.components import discovery, group, zone
from homeassistant.config import load_yaml_config_file
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.util as util
import homeassistant.util.dt as dt_util

from homeassistant.helpers.event import track_utc_time_change
from homeassistant.const import (
    ATTR_GPS_ACCURACY, ATTR_LATITUDE, ATTR_LONGITUDE,
    DEVICE_DEFAULT_NAME, STATE_HOME, STATE_NOT_HOME)

DOMAIN = "device_tracker"
DEPENDENCIES = ['zone']

GROUP_NAME_ALL_DEVICES = 'all devices'
ENTITY_ID_ALL_DEVICES = group.ENTITY_ID_FORMAT.format('all_devices')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

YAML_DEVICES = 'known_devices.yaml'

CONF_TRACK_NEW = "track_new_devices"
DEFAULT_CONF_TRACK_NEW = True

CONF_CONSIDER_HOME = 'consider_home'
DEFAULT_CONSIDER_HOME = 180  # seconds

CONF_SCAN_INTERVAL = "interval_seconds"
DEFAULT_SCAN_INTERVAL = 12

CONF_AWAY_HIDE = 'hide_if_away'
DEFAULT_AWAY_HIDE = False

CONF_HOME_RANGE = 'home_range'
DEFAULT_HOME_RANGE = 100

SERVICE_SEE = 'see'

ATTR_MAC = 'mac'
ATTR_DEV_ID = 'dev_id'
ATTR_HOST_NAME = 'host_name'
ATTR_LOCATION_NAME = 'location_name'
ATTR_GPS = 'gps'
ATTR_BATTERY = 'battery'

DISCOVERY_PLATFORMS = {
    discovery.SERVICE_NETGEAR: 'netgear',
}
_LOGGER = logging.getLogger(__name__)

# pylint: disable=too-many-arguments


def is_on(hass, entity_id=None):
    """Return the state if any or a specified device is home."""
    entity = entity_id or ENTITY_ID_ALL_DEVICES

    return hass.states.is_state(entity, STATE_HOME)


def see(hass, mac=None, dev_id=None, host_name=None, location_name=None,
        gps=None, gps_accuracy=None, battery=None):
    """Call service to notify you see device."""
    data = {key: value for key, value in
            ((ATTR_MAC, mac),
             (ATTR_DEV_ID, dev_id),
             (ATTR_HOST_NAME, host_name),
             (ATTR_LOCATION_NAME, location_name),
             (ATTR_GPS, gps),
             (ATTR_GPS_ACCURACY, gps_accuracy),
             (ATTR_BATTERY, battery)) if value is not None}
    hass.services.call(DOMAIN, SERVICE_SEE, data)


def setup(hass, config):
    """Setup device tracker."""
    yaml_path = hass.config.path(YAML_DEVICES)

    conf = config.get(DOMAIN, {})
    if isinstance(conf, list) and len(conf) > 0:
        conf = conf[0]
    consider_home = timedelta(
        seconds=util.convert(conf.get(CONF_CONSIDER_HOME), int,
                             DEFAULT_CONSIDER_HOME))
    track_new = util.convert(conf.get(CONF_TRACK_NEW), bool,
                             DEFAULT_CONF_TRACK_NEW)
    home_range = util.convert(conf.get(CONF_HOME_RANGE), int,
                              DEFAULT_HOME_RANGE)

    devices = load_config(yaml_path, hass, consider_home, home_range)
    tracker = DeviceTracker(hass, consider_home, track_new, home_range,
                            devices)

    def setup_platform(p_type, p_config, disc_info=None):
        """Setup a device tracker platform."""
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

    for p_type, p_config in config_per_platform(config, DOMAIN):
        setup_platform(p_type, p_config)

    def device_tracker_discovered(service, info):
        """Called when a device tracker platform is discovered."""
        setup_platform(DISCOVERY_PLATFORMS[service], {}, info)

    discovery.listen(hass, DISCOVERY_PLATFORMS.keys(),
                     device_tracker_discovered)

    def update_stale(now):
        """Clean up stale devices."""
        tracker.update_stale(now)
    track_utc_time_change(hass, update_stale, second=range(0, 60, 5))

    tracker.setup_group()

    def see_service(call):
        """Service to see a device."""
        args = {key: value for key, value in call.data.items() if key in
                (ATTR_MAC, ATTR_DEV_ID, ATTR_HOST_NAME, ATTR_LOCATION_NAME,
                 ATTR_GPS, ATTR_GPS_ACCURACY, ATTR_BATTERY)}
        tracker.see(**args)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_SEE, see_service,
                           descriptions.get(SERVICE_SEE))

    return True


class DeviceTracker(object):
    """Representation of a device tracker."""

    def __init__(self, hass, consider_home, track_new, home_range, devices):
        """Initialize a device tracker."""
        self.hass = hass
        self.devices = {dev.dev_id: dev for dev in devices}
        self.mac_to_dev = {dev.mac: dev for dev in devices if dev.mac}
        self.consider_home = consider_home
        self.track_new = track_new
        self.home_range = home_range
        self.lock = threading.Lock()

        for device in devices:
            if device.track:
                device.update_ha_state()

        self.group = None

    def see(self, mac=None, dev_id=None, host_name=None, location_name=None,
            gps=None, gps_accuracy=None, battery=None):
        """Notify the device tracker that you see a device."""
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
                device.seen(host_name, location_name, gps, gps_accuracy,
                            battery)
                if device.track:
                    device.update_ha_state()
                return

            # If no device can be found, create it
            dev_id = util.ensure_unique_string(dev_id, self.devices.keys())
            device = Device(
                self.hass, self.consider_home, self.home_range, self.track_new,
                dev_id, mac, (host_name or dev_id).replace('_', ' '))
            self.devices[dev_id] = device
            if mac is not None:
                self.mac_to_dev[mac] = device

            device.seen(host_name, location_name, gps, gps_accuracy, battery)
            if device.track:
                device.update_ha_state()

            # During init, we ignore the group
            if self.group is not None:
                self.group.update_tracked_entity_ids(
                    list(self.group.tracking) + [device.entity_id])
            update_config(self.hass.config.path(YAML_DEVICES), dev_id, device)

    def setup_group(self):
        """Initialize group for all tracked devices."""
        entity_ids = (dev.entity_id for dev in self.devices.values()
                      if dev.track)
        self.group = group.Group(
            self.hass, GROUP_NAME_ALL_DEVICES, entity_ids, False)

    def update_stale(self, now):
        """Update stale devices."""
        with self.lock:
            for device in self.devices.values():
                if (device.track and device.last_update_home and
                        device.stale(now)):
                    device.update_ha_state(True)


class Device(Entity):
    """Represent a tracked device."""

    host_name = None
    location_name = None
    gps = None
    gps_accuracy = 0
    last_seen = None
    battery = None

    # Track if the last update of this device was HOME.
    last_update_home = False
    _state = STATE_NOT_HOME

    def __init__(self, hass, consider_home, home_range, track, dev_id, mac,
                 name=None, picture=None, away_hide=False):
        """Initialize a device."""
        self.hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(dev_id)

        # Timedelta object how long we consider a device home if it is not
        # detected anymore.
        self.consider_home = consider_home

        # Distance in meters
        self.home_range = home_range
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
    def gps_home(self):
        """Return if device is within range of home."""
        distance = max(
            0, self.hass.config.distance(*self.gps) - self.gps_accuracy)
        return self.gps is not None and distance <= self.home_range

    @property
    def name(self):
        """Return the name of the entity."""
        return self.config_name or self.host_name or DEVICE_DEFAULT_NAME

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def entity_picture(self):
        """Return the picture of the device."""
        return self.config_picture

    @property
    def state_attributes(self):
        """Return the device state attributes."""
        attr = {}

        if self.gps:
            attr[ATTR_LATITUDE] = self.gps[0]
            attr[ATTR_LONGITUDE] = self.gps[1]
            attr[ATTR_GPS_ACCURACY] = self.gps_accuracy

        if self.battery:
            attr[ATTR_BATTERY] = self.battery

        return attr

    @property
    def hidden(self):
        """If device should be hidden."""
        return self.away_hide and self.state != STATE_HOME

    def seen(self, host_name=None, location_name=None, gps=None,
             gps_accuracy=0, battery=None):
        """Mark the device as seen."""
        self.last_seen = dt_util.utcnow()
        self.host_name = host_name
        self.location_name = location_name
        self.gps_accuracy = gps_accuracy or 0
        self.battery = battery
        if gps is None:
            self.gps = None
        else:
            try:
                self.gps = tuple(float(val) for val in gps)
            except ValueError:
                _LOGGER.warning('Could not parse gps value for %s: %s',
                                self.dev_id, gps)
                self.gps = None
        self.update()

    def stale(self, now=None):
        """Return if device state is stale."""
        return self.last_seen and \
            (now or dt_util.utcnow()) - self.last_seen > self.consider_home

    def update(self):
        """Update state of entity."""
        if not self.last_seen:
            return
        elif self.location_name:
            self._state = self.location_name
        elif self.gps is not None:
            zone_state = zone.active_zone(self.hass, self.gps[0], self.gps[1],
                                          self.gps_accuracy)
            if zone_state is None:
                self._state = STATE_NOT_HOME
            elif zone_state.entity_id == zone.ENTITY_ID_HOME:
                self._state = STATE_HOME
            else:
                self._state = zone_state.name

        elif self.stale():
            self._state = STATE_NOT_HOME
            self.last_update_home = False
        else:
            self._state = STATE_HOME
            self.last_update_home = True


def load_config(path, hass, consider_home, home_range):
    """Load devices from YAML configuration file."""
    if not os.path.isfile(path):
        return []
    return [
        Device(hass, consider_home, home_range, device.get('track', False),
               str(dev_id).lower(), str(device.get('mac')).upper(),
               device.get('name'), device.get('picture'),
               device.get(CONF_AWAY_HIDE, DEFAULT_AWAY_HIDE))
        for dev_id, device in load_yaml_config_file(path).items()]


def setup_scanner_platform(hass, config, scanner, see_device):
    """Helper method to connect scanner-based platform to device tracker."""
    interval = util.convert(config.get(CONF_SCAN_INTERVAL), int,
                            DEFAULT_SCAN_INTERVAL)

    # Initial scan of each mac we also tell about host name for config
    seen = set()

    def device_tracker_scan(now):
        """Called when interval matches."""
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
    """Add device to YAML configuration file."""
    with open(path, 'a') as out:
        out.write('\n')
        out.write('{}:\n'.format(device.dev_id))

        for key, value in (('name', device.name), ('mac', device.mac),
                           ('picture', device.config_picture),
                           ('track', 'yes' if device.track else 'no'),
                           (CONF_AWAY_HIDE,
                            'yes' if device.away_hide else 'no')):
            out.write('  {}: {}\n'.format(key, '' if value is None else value))
