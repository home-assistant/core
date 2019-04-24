"""Support for Life360 device tracking."""

from collections import namedtuple
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL,
    ENTITY_ID_FORMAT as DT_ENTITY_ID_FORMAT, PLATFORM_SCHEMA)
from homeassistant.components.zone import (
    DEFAULT_PASSIVE, ENTITY_ID_FORMAT as ZN_ENTITY_ID_FORMAT, ENTITY_ID_HOME,
    Zone)
from homeassistant.components.zone.zone import active_zone
from homeassistant.const import (
    ATTR_BATTERY_CHARGING, ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, ATTR_LATITUDE,
    ATTR_LONGITUDE, ATTR_NAME, CONF_EXCLUDE, CONF_FILENAME, CONF_INCLUDE,
    CONF_PASSWORD, CONF_PREFIX, CONF_USERNAME, LENGTH_FEET, LENGTH_KILOMETERS,
    LENGTH_METERS, LENGTH_MILES, STATE_HOME, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import track_time_interval
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.util.distance import convert
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_FILENAME = 'life360.conf'
DEFAULT_HOME_PLACE = 'Home'
SPEED_FACTOR_MPH = 2.25
MIN_ZONE_INTERVAL = timedelta(minutes=1)
EVENT_DELAY = timedelta(seconds=30)

DOMAIN = 'life360'
DATA_LIFE360 = DOMAIN
DEFAULT_PREFIX = DOMAIN

_API_TOKEN = 'cFJFcXVnYWJSZXRyZTRFc3RldGhlcnVmcmVQdW1hbUV4dWNyRU'\
             'h1YzptM2ZydXBSZXRSZXN3ZXJFQ2hBUHJFOTZxYWtFZHI0Vg=='

CONF_ADD_ZONES = 'add_zones'
CONF_CIRCLES = 'circles'
CONF_DRIVING_SPEED = 'driving_speed'
CONF_ERROR_THRESHOLD = 'error_threshold'
CONF_HOME_PLACE = 'home_place'
CONF_MAX_GPS_ACCURACY = 'max_gps_accuracy'
CONF_MAX_UPDATE_WAIT = 'max_update_wait'
CONF_MEMBERS = 'members'
CONF_PLACES = 'places'
CONF_SHOW_AS_STATE = 'show_as_state'
CONF_WARNING_THRESHOLD = 'warning_threshold'

AZ_ONCE = 'once'
SHOW_DRIVING = 'driving'
SHOW_MOVING = 'moving'
SHOW_PLACES = 'places'
SHOW_AS_STATE_OPTS = [SHOW_DRIVING, SHOW_MOVING, SHOW_PLACES]

ATTR_ADDRESS = 'address'
ATTR_AT_LOC_SINCE = 'at_loc_since'
ATTR_DRIVING = SHOW_DRIVING
ATTR_LAST_SEEN = 'last_seen'
ATTR_MOVING = SHOW_MOVING
ATTR_RADIUS = 'radius'
ATTR_RAW_SPEED = 'raw_speed'
ATTR_SPEED = 'speed'
ATTR_WAIT = 'wait'
ATTR_WIFI_ON = 'wifi_on'

SERVICE_ZONES_FROM_PLACES = 'zones_from_places'

EVENT_UPDATE_OVERDUE = 'life360_update_overdue'
EVENT_UPDATE_RESTORED = 'life360_update_restored'


def _excl_incl_list_to_filter_dict(value):
    return {
        'include': CONF_INCLUDE in value,
        'list': value.get(CONF_EXCLUDE) or value.get(CONF_INCLUDE)
    }


def _prefix(value):
    if not value:
        return ''
    if not value.endswith('_'):
        return value + '_'
    return value


def _thresholds(config):
    error_threshold = config.get(CONF_ERROR_THRESHOLD)
    warning_threshold = config.get(CONF_WARNING_THRESHOLD)
    if error_threshold and warning_threshold:
        if error_threshold <= warning_threshold:
            raise vol.Invalid('{} must be larger than {}'.format(
                CONF_ERROR_THRESHOLD, CONF_WARNING_THRESHOLD))
    elif not error_threshold and warning_threshold:
        config[CONF_ERROR_THRESHOLD] = warning_threshold + 1
    elif error_threshold and not warning_threshold:
        # Make them the same which effectively prevents warnings.
        config[CONF_WARNING_THRESHOLD] = error_threshold
    else:
        # Log all errors as errors.
        config[CONF_ERROR_THRESHOLD] = 1
        config[CONF_WARNING_THRESHOLD] = 1
    return config


_SLUG_LIST = vol.All(
    cv.ensure_list, [cv.slugify],
    vol.Length(min=1, msg='List cannot be empty'))

_LOWER_STRING_LIST = vol.All(
    cv.ensure_list, [vol.All(cv.string, vol.Lower)],
    vol.Length(min=1, msg='List cannot be empty'))

_EXCL_INCL_SLUG_LIST = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_EXCLUDE, 'incl_excl'): _SLUG_LIST,
        vol.Exclusive(CONF_INCLUDE, 'incl_excl'): _SLUG_LIST,
    }),
    cv.has_at_least_one_key(CONF_EXCLUDE, CONF_INCLUDE),
    _excl_incl_list_to_filter_dict,
)

_EXCL_INCL_LOWER_STRING_LIST = vol.All(
    vol.Schema({
        vol.Exclusive(CONF_EXCLUDE, 'incl_excl'): _LOWER_STRING_LIST,
        vol.Exclusive(CONF_INCLUDE, 'incl_excl'): _LOWER_STRING_LIST,
    }),
    cv.has_at_least_one_key(CONF_EXCLUDE, CONF_INCLUDE),
    _excl_incl_list_to_filter_dict
)

_THRESHOLD = vol.All(vol.Coerce(int), vol.Range(min=1))

LIFE360_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_ADD_ZONES): vol.Any(
        AZ_ONCE, vol.All(cv.time_period, vol.Range(min=MIN_ZONE_INTERVAL))),
    vol.Optional(CONF_CIRCLES): _EXCL_INCL_LOWER_STRING_LIST,
    vol.Optional(CONF_DRIVING_SPEED): vol.Coerce(float),
    vol.Optional(CONF_ERROR_THRESHOLD): _THRESHOLD,
    vol.Optional(CONF_FILENAME, default=DEFAULT_FILENAME): cv.string,
    vol.Optional(CONF_HOME_PLACE, default=DEFAULT_HOME_PLACE): cv.string,
    vol.Optional(CONF_MAX_GPS_ACCURACY): vol.Coerce(float),
    vol.Optional(CONF_MAX_UPDATE_WAIT): vol.All(
        cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_MEMBERS): _EXCL_INCL_SLUG_LIST,
    vol.Optional(CONF_PLACES): _EXCL_INCL_LOWER_STRING_LIST,
    vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX):
        vol.All(vol.Any(None, cv.string), _prefix),
    vol.Optional(CONF_SHOW_AS_STATE, default=[]): vol.All(
        cv.ensure_list, [vol.In(SHOW_AS_STATE_OPTS)]),
    vol.Optional(CONF_WARNING_THRESHOLD): _THRESHOLD,
})

PLATFORM_SCHEMA = vol.All(LIFE360_SCHEMA, _thresholds)


def _include_name(filter_dict, name):
    if not name:
        return False
    if not filter_dict:
        return True
    name = name.lower()
    if filter_dict['include']:
        return name in filter_dict['list']
    return name not in filter_dict['list']


def _exc_msg(exc):
    return '{}: {}'.format(exc.__class__.__name__, str(exc))


def _setup_zone_updating(hass, config, api):
    from life360 import Life360Error

    add_zones = config.get(CONF_ADD_ZONES)
    if not add_zones:
        return

    Place = namedtuple(
        'Place', [ATTR_NAME, ATTR_LATITUDE, ATTR_LONGITUDE, ATTR_RADIUS])

    def get_places(api, circles_filter, places_filter):
        errs = 0
        while True:
            places = set()
            try:
                for circle in api.get_circles():
                    circle_id = circle['id']
                    if not (circle_id
                            and _include_name(circles_filter, circle['name'])):
                        continue
                    for place in api.get_circle_places(circle_id):
                        place_name = place['name']
                        if not _include_name(places_filter, place_name):
                            continue
                        places.add(Place(place_name,
                                         float(place['latitude']),
                                         float(place['longitude']),
                                         float(place['radius'])))
            except (Life360Error, KeyError, TypeError, ValueError) as exc:
                errs += 1
                if errs >= 3:
                    _LOGGER.error('get_places: %s', _exc_msg(exc))
                    return None
            else:
                return places

    def zone_from_place(place, entity_id=None):
        zone = Zone(hass, *place, None, DEFAULT_PASSIVE)
        zone.entity_id = (
            entity_id or
            generate_entity_id(ZN_ENTITY_ID_FORMAT, place.name, None, hass))
        zone.schedule_update_ha_state()
        return zone

    def log_places(msg, places):
        plural = 's' if len(places) > 1 else ''
        _LOGGER.debug(
            '%s zone%s from Place%s: %s',
            msg, plural, plural,
            '; '.join(['{}: {}, {}, {}'.format(*place) for place
                       in sorted(places, key=lambda x: x.name.lower())]))

    def zones_from_places(api, circles_filter, places_filter, home_place_name,
                          zones):
        _LOGGER.debug('Checking Places')
        places = get_places(api, circles_filter, places_filter)
        if places is None:
            return

        # See if there is a Life360 Place whose name matches CONF_HOME_PLACE.
        # If there is, remove it from set and handle it specially.
        home_place = None
        for place in places.copy():
            if place.name.lower() == home_place_name:
                home_place = place
                places.discard(place)
                break

        # If a "Home Place" was found and it is different from the current
        # zone.home, then update zone.home with it.
        if home_place:
            hz_attrs = hass.states.get(ENTITY_ID_HOME).attributes
            if home_place != Place(hz_attrs[ATTR_FRIENDLY_NAME],
                                   hz_attrs[ATTR_LATITUDE],
                                   hz_attrs[ATTR_LONGITUDE],
                                   hz_attrs[ATTR_RADIUS]):
                log_places('Updating', [home_place])
                zone_from_place(home_place, ENTITY_ID_HOME)

        # Do any of the Life360 Places that we created HA zones from no longer
        # exist? If so, remove the corresponding zones.
        remove_places = set(zones.keys()) - places
        if remove_places:
            log_places('Removing', remove_places)
            for remove_place in remove_places:
                run_coroutine_threadsafe(
                    zones.pop(remove_place).async_remove(), hass.loop).result()

        # Are there any newly defined Life360 Places since the last time we
        # checked? If so, create HA zones for them.
        add_places = places - set(zones.keys())
        if add_places:
            log_places('Adding', add_places)
            for add_place in add_places:
                zones[add_place] = zone_from_place(add_place)

    circles_filter = config.get(CONF_CIRCLES)
    places_filter = config.get(CONF_PLACES)
    home_place_name = config[CONF_HOME_PLACE].lower()
    zones = {}

    def zones_from_places_interval(now=None):
        zones_from_places(
            api, circles_filter, places_filter, home_place_name, zones)

    def zones_from_places_service(service):
        for params in hass.data[DATA_LIFE360]:
            zones_from_places(*params)

    zones_from_places_interval()
    if add_zones != AZ_ONCE:
        _LOGGER.debug('Will check Places every: %s', add_zones)
        track_time_interval(hass, zones_from_places_interval, add_zones)
    hass.data.setdefault(DATA_LIFE360, []).append(
        (api, circles_filter, places_filter, home_place_name, zones))
    if not hass.services.has_service(DOMAIN, SERVICE_ZONES_FROM_PLACES):
        hass.services.register(
            DOMAIN, SERVICE_ZONES_FROM_PLACES, zones_from_places_service)


def _dump_filter(filter_dict, desc, func=lambda x: x):
    if not filter_dict:
        return
    _LOGGER.debug(
        '%scluding %s: %s',
        'In' if filter_dict['include'] else 'Ex', desc,
        ', '.join([func(name) for name in filter_dict['list']]))


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up device scanner."""
    interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    try:
        from life360 import life360, LoginError
        api = life360(_API_TOKEN, config[CONF_USERNAME], config[CONF_PASSWORD],
                      timeout=3.05,
                      authorization_cache_file=hass.config.path(
                          config[CONF_FILENAME]),
                      max_retries=2)
        # Test credentials and communications.
        api.get_circles()
    except LoginError as exc:
        _LOGGER.error(_exc_msg(exc))
        _LOGGER.error('Aborting setup!')
        return False
    # Ignore other errors at this time. Hopefully they're temporary.
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.warning('Ignoring: %s', _exc_msg(exc))

    _dump_filter(config.get(CONF_CIRCLES), 'Circles')
    _dump_filter(config.get(CONF_PLACES), 'Places')

    _setup_zone_updating(hass, config, api)

    Life360Scanner(hass, config, see, interval, api)
    _LOGGER.debug('Setup successful!')
    return True


def _utc_from_ts(val):
    try:
        return dt_util.utc_from_timestamp(float(val))
    except (TypeError, ValueError):
        return None


def _dt_attr_from_ts(timestamp):
    utc = _utc_from_ts(timestamp)
    if utc:
        return utc
    return STATE_UNKNOWN


def _bool_attr_from_int(val):
    try:
        return bool(int(val))
    except (TypeError, ValueError):
        return STATE_UNKNOWN


class Life360Scanner:
    """Life360 device scanner."""

    def __init__(self, hass, config, see, interval, api):
        """Initialize Life360Scanner."""
        self._hass = hass
        self._see = see
        self._show_as_state = config[CONF_SHOW_AS_STATE]
        self._home_place_name = config[CONF_HOME_PLACE].lower()
        self._max_gps_accuracy = config.get(CONF_MAX_GPS_ACCURACY)
        self._max_update_wait = config.get(CONF_MAX_UPDATE_WAIT)
        self._prefix = config[CONF_PREFIX]
        self._circles_filter = config.get(CONF_CIRCLES)
        self._members_filter = config.get(CONF_MEMBERS)
        self._places_filter = config.get(CONF_PLACES)
        self._driving_speed = config.get(CONF_DRIVING_SPEED)
        self._api = api
        self._errs = {}
        self._error_threshold = config[CONF_ERROR_THRESHOLD]
        self._warning_threshold = config[CONF_WARNING_THRESHOLD]
        self._max_errs = self._error_threshold + 1
        self._dev_data = {}
        self._members_seen = set()
        self._circles_seen = set()

        _dump_filter(self._members_filter, 'device IDs', self._dev_id)

        self._started = dt_util.utcnow()
        self._updated_at_least_one_member = False
        self._update_life360()
        if not self._updated_at_least_one_member:
            _LOGGER.warning(
                'Did not find any Life360 Members to track! '
                'Check, or remove, cirles and members configuration variables.'
            )
        track_time_interval(self._hass, self._update_life360, interval)

    def _dev_id(self, name):
        return self._prefix + name

    def _ok(self, key):
        if self._errs.get(key, 0) >= self._max_errs:
            _LOGGER.error('%s: OK again', key)
        self._errs[key] = 0

    def _err(self, key, err_msg):
        _errs = self._errs.get(key, 0)
        if _errs < self._max_errs:
            self._errs[key] = _errs = _errs + 1
            msg = '{}: {}'.format(key, err_msg)
            if _errs >= self._error_threshold:
                if _errs == self._max_errs:
                    msg = 'Suppressing further errors until OK: ' + msg
                _LOGGER.error(msg)
            elif _errs >= self._warning_threshold:
                _LOGGER.warning(msg)

    def _exc(self, key, exc):
        self._err(key, _exc_msg(exc))

    def _update_member(self, member, dev_id):
        prev_seen, reported = self._dev_data.get(dev_id, (None, False))

        loc = member.get('location', {})
        last_seen = _utc_from_ts(loc.get('timestamp'))

        if self._max_update_wait:
            now = dt_util.utcnow()
            update = last_seen or prev_seen or self._started
            overdue = now - update > self._max_update_wait
            if overdue and not reported and now - self._started > EVENT_DELAY:
                self._hass.bus.fire(
                    EVENT_UPDATE_OVERDUE,
                    {ATTR_ENTITY_ID: DT_ENTITY_ID_FORMAT.format(dev_id)})
                reported = True
            elif not overdue and reported:
                self._hass.bus.fire(
                    EVENT_UPDATE_RESTORED, {
                        ATTR_ENTITY_ID: DT_ENTITY_ID_FORMAT.format(dev_id),
                        ATTR_WAIT:
                            str(last_seen - (prev_seen or self._started))
                            .split('.')[0]})
                reported = False

        self._dev_data[dev_id] = last_seen or prev_seen, reported

        if not loc:
            err_msg = member['issues']['title']
            if err_msg:
                if member['issues']['dialog']:
                    err_msg += ': ' + member['issues']['dialog']
            else:
                err_msg = 'Location information missing'
            self._err(dev_id, err_msg)
            return

        if last_seen and (not prev_seen or last_seen > prev_seen):
            lat = loc.get('latitude')
            lon = loc.get('longitude')
            gps_accuracy = loc.get('accuracy')
            try:
                lat = float(lat)
                lon = float(lon)
                # Life360 reports accuracy in feet, but Device Tracker expects
                # gps_accuracy in meters.
                gps_accuracy = round(
                    convert(float(gps_accuracy), LENGTH_FEET, LENGTH_METERS))
            except (TypeError, ValueError):
                self._err(dev_id, 'GPS data invalid: {}, {}, {}'.format(
                    lat, lon, gps_accuracy))
                return

            self._ok(dev_id)

            msg = 'Updating {}'.format(dev_id)
            if prev_seen:
                msg += '; Time since last update: {}'.format(
                    last_seen - prev_seen)
            _LOGGER.debug(msg)

            if (self._max_gps_accuracy is not None and
                    gps_accuracy > self._max_gps_accuracy):
                _LOGGER.warning(
                    '%s: Ignoring update because expected GPS '
                    'accuracy (%.0f) is not met: %.0f',
                    dev_id, self._max_gps_accuracy, gps_accuracy)
                return

            # Convert empty string to None.
            place_name = loc.get('name') or None
            if not _include_name(self._places_filter, place_name):
                place_name = None

            # Does user want location name to be shown as state?
            if SHOW_PLACES in self._show_as_state:
                loc_name = place_name
                # Make sure Home Place is always seen exactly as home,
                # which is the special device_tracker state for home.
                if loc_name and loc_name.lower() == self._home_place_name:
                    loc_name = STATE_HOME
            else:
                loc_name = None

            # If a place name is given, then address will just be a copy of
            # it, so don't bother with address. Otherwise, piece address
            # lines together, depending on which are present.
            if place_name:
                address = None
            else:
                address1 = loc.get('address1') or None
                address2 = loc.get('address2') or None
                if address1 and address2:
                    address = ', '.join([address1, address2])
                else:
                    address = address1 or address2

            raw_speed = loc.get('speed')
            try:
                speed = float(raw_speed) * SPEED_FACTOR_MPH
                if self._hass.config.units.is_metric:
                    speed = convert(speed, LENGTH_MILES, LENGTH_KILOMETERS)
                speed = max(0, round(speed))
            except (TypeError, ValueError):
                speed = STATE_UNKNOWN
            driving = _bool_attr_from_int(loc.get('isDriving'))
            if (driving in (STATE_UNKNOWN, False) and
                    self._driving_speed is not None and
                    speed != STATE_UNKNOWN):
                driving = speed >= self._driving_speed
            moving = _bool_attr_from_int(loc.get('inTransit'))

            attrs = {
                ATTR_ADDRESS: address,
                ATTR_AT_LOC_SINCE: _dt_attr_from_ts(loc.get('since')),
                ATTR_BATTERY_CHARGING: _bool_attr_from_int(loc.get('charge')),
                ATTR_DRIVING: driving,
                ATTR_LAST_SEEN: last_seen,
                ATTR_MOVING: moving,
                ATTR_RAW_SPEED: raw_speed,
                ATTR_SPEED: speed,
                ATTR_WIFI_ON: _bool_attr_from_int(loc.get('wifiState')),
            }

            # If we don't have a location name yet and user wants driving or
            # moving to be shown as state, and current location is not in a HA
            # zone, then update location name accordingly.
            if not loc_name and not active_zone(
                    self._hass, lat, lon, gps_accuracy):
                if SHOW_DRIVING in self._show_as_state and driving is True:
                    loc_name = SHOW_DRIVING.capitalize()
                elif SHOW_MOVING in self._show_as_state and moving is True:
                    loc_name = SHOW_MOVING.capitalize()

            try:
                battery = int(float(loc.get('battery')))
            except (TypeError, ValueError):
                battery = None

            self._see(dev_id=dev_id, location_name=loc_name, gps=(lat, lon),
                      gps_accuracy=gps_accuracy, battery=battery,
                      attributes=attrs, picture=member.get('avatar'))

    def _update_life360(self, now=None):
        from life360 import Life360Error

        checked_ids = []

        err_key = 'get_circles'
        try:
            circles = self._api.get_circles()
        except Life360Error as exc:
            self._exc(err_key, exc)
            return
        self._ok(err_key)

        for circle in circles:
            circle_name = circle.get('name')
            circle_id = circle.get('id')
            if not circle_name or not circle_id:
                continue
            include_circle = _include_name(self._circles_filter, circle_name)
            if circle_name not in self._circles_seen:
                self._circles_seen.add(circle_name)
                _LOGGER.debug(
                    '%s Circle: will%s be included', circle_name,
                    '' if include_circle else ' NOT')
            if not include_circle:
                continue
            err_key = 'get_circle "{}"'.format(circle_name)
            try:
                members = self._api.get_circle_members(circle_id)
            except Life360Error as exc:
                self._exc(err_key, exc)
                continue
            self._ok(err_key)

            for member in members:
                err_key = 'Member data'
                try:
                    m_id = member['id']
                    first = member.get('firstName')
                    last = member.get('lastName')
                    if first and last:
                        full_name = ' '.join([first, last])
                    else:
                        full_name = first or last
                    name = cv.slugify(full_name)
                    include_member = _include_name(self._members_filter, name)
                    dev_id = self._dev_id(name)
                    if full_name not in self._members_seen:
                        self._members_seen.add(full_name)
                        _LOGGER.debug(
                            '%s -> %s: will%s be tracked', full_name,
                            dev_id,
                            '' if include_member else ' NOT')
                    sharing = bool(int(member['features']['shareLocation']))
                except (KeyError, TypeError, ValueError, vol.Invalid):
                    self._err(err_key, member)
                    continue
                self._ok(err_key)

                if m_id not in checked_ids and include_member and sharing:
                    checked_ids.append(m_id)
                    self._updated_at_least_one_member = True
                    self._update_member(member, dev_id)
