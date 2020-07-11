"""Support for Life360 device tracking."""
from datetime import timedelta
import logging

from life360 import Life360Error
import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.components.zone import async_active_zone
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_ENTITY_ID,
    CONF_PREFIX,
    LENGTH_FEET,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    STATE_UNKNOWN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.distance import convert
import homeassistant.util.dt as dt_util

from .const import (
    CONF_CIRCLES,
    CONF_DRIVING_SPEED,
    CONF_ERROR_THRESHOLD,
    CONF_MAX_GPS_ACCURACY,
    CONF_MAX_UPDATE_WAIT,
    CONF_MEMBERS,
    CONF_SHOW_AS_STATE,
    CONF_WARNING_THRESHOLD,
    DOMAIN,
    SHOW_DRIVING,
    SHOW_MOVING,
)

_LOGGER = logging.getLogger(__name__)

SPEED_FACTOR_MPH = 2.25
EVENT_DELAY = timedelta(seconds=30)

ATTR_ADDRESS = "address"
ATTR_AT_LOC_SINCE = "at_loc_since"
ATTR_DRIVING = "driving"
ATTR_LAST_SEEN = "last_seen"
ATTR_MOVING = "moving"
ATTR_PLACE = "place"
ATTR_RAW_SPEED = "raw_speed"
ATTR_SPEED = "speed"
ATTR_WAIT = "wait"
ATTR_WIFI_ON = "wifi_on"

EVENT_UPDATE_OVERDUE = "life360_update_overdue"
EVENT_UPDATE_RESTORED = "life360_update_restored"


def _include_name(filter_dict, name):
    if not name:
        return False
    if not filter_dict:
        return True
    name = name.lower()
    if filter_dict["include"]:
        return name in filter_dict["list"]
    return name not in filter_dict["list"]


def _exc_msg(exc):
    return f"{exc.__class__.__name__}: {exc}"


def _dump_filter(filter_dict, desc, func=lambda x: x):
    if not filter_dict:
        return
    _LOGGER.debug(
        "%scluding %s: %s",
        "In" if filter_dict["include"] else "Ex",
        desc,
        ", ".join([func(name) for name in filter_dict["list"]]),
    )


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up device scanner."""
    config = hass.data[DOMAIN]["config"]
    apis = hass.data[DOMAIN]["apis"]
    Life360Scanner(hass, config, see, apis)
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

    def __init__(self, hass, config, see, apis):
        """Initialize Life360Scanner."""
        self._hass = hass
        self._see = see
        self._max_gps_accuracy = config.get(CONF_MAX_GPS_ACCURACY)
        self._max_update_wait = config.get(CONF_MAX_UPDATE_WAIT)
        self._prefix = config[CONF_PREFIX]
        self._circles_filter = config.get(CONF_CIRCLES)
        self._members_filter = config.get(CONF_MEMBERS)
        self._driving_speed = config.get(CONF_DRIVING_SPEED)
        self._show_as_state = config[CONF_SHOW_AS_STATE]
        self._apis = apis
        self._errs = {}
        self._error_threshold = config[CONF_ERROR_THRESHOLD]
        self._warning_threshold = config[CONF_WARNING_THRESHOLD]
        self._max_errs = self._error_threshold + 1
        self._dev_data = {}
        self._circles_logged = set()
        self._members_logged = set()

        _dump_filter(self._circles_filter, "Circles")
        _dump_filter(self._members_filter, "device IDs", self._dev_id)

        self._started = dt_util.utcnow()
        self._update_life360()
        track_time_interval(
            self._hass, self._update_life360, config[CONF_SCAN_INTERVAL]
        )

    def _dev_id(self, name):
        return self._prefix + name

    def _ok(self, key):
        if self._errs.get(key, 0) >= self._max_errs:
            _LOGGER.error("%s: OK again", key)
        self._errs[key] = 0

    def _err(self, key, err_msg):
        _errs = self._errs.get(key, 0)
        if _errs < self._max_errs:
            self._errs[key] = _errs = _errs + 1
            msg = f"{key}: {err_msg}"
            if _errs >= self._error_threshold:
                if _errs == self._max_errs:
                    msg = f"Suppressing further errors until OK: {msg}"
                _LOGGER.error(msg)
            elif _errs >= self._warning_threshold:
                _LOGGER.warning(msg)

    def _exc(self, key, exc):
        self._err(key, _exc_msg(exc))

    def _prev_seen(self, dev_id, last_seen):
        prev_seen, reported = self._dev_data.get(dev_id, (None, False))

        if self._max_update_wait:
            now = dt_util.utcnow()
            most_recent_update = last_seen or prev_seen or self._started
            overdue = now - most_recent_update > self._max_update_wait
            if overdue and not reported and now - self._started > EVENT_DELAY:
                self._hass.bus.fire(
                    EVENT_UPDATE_OVERDUE,
                    {ATTR_ENTITY_ID: f"{DEVICE_TRACKER_DOMAIN}.{dev_id}"},
                )
                reported = True
            elif not overdue and reported:
                self._hass.bus.fire(
                    EVENT_UPDATE_RESTORED,
                    {
                        ATTR_ENTITY_ID: f"{DEVICE_TRACKER_DOMAIN}.{dev_id}",
                        ATTR_WAIT: str(last_seen - (prev_seen or self._started)).split(
                            "."
                        )[0],
                    },
                )
                reported = False

        # Don't remember last_seen unless it's really an update.
        if not last_seen or prev_seen and last_seen <= prev_seen:
            last_seen = prev_seen
        self._dev_data[dev_id] = last_seen, reported

        return prev_seen

    def _update_member(self, member, dev_id):
        loc = member.get("location")
        try:
            last_seen = _utc_from_ts(loc.get("timestamp"))
        except AttributeError:
            last_seen = None
        prev_seen = self._prev_seen(dev_id, last_seen)

        if not loc:
            err_msg = member["issues"]["title"]
            if err_msg:
                if member["issues"]["dialog"]:
                    err_msg += f": {member['issues']['dialog']}"
            else:
                err_msg = "Location information missing"
            self._err(dev_id, err_msg)
            return

        # Only update when we truly have an update.
        if not last_seen:
            _LOGGER.warning("%s: Ignoring update because timestamp is missing", dev_id)
            return
        if prev_seen and last_seen < prev_seen:
            _LOGGER.warning(
                "%s: Ignoring update because timestamp is older than last timestamp",
                dev_id,
            )
            _LOGGER.debug("%s < %s", last_seen, prev_seen)
            return
        if last_seen == prev_seen:
            return

        lat = loc.get("latitude")
        lon = loc.get("longitude")
        gps_accuracy = loc.get("accuracy")
        try:
            lat = float(lat)
            lon = float(lon)
            # Life360 reports accuracy in feet, but Device Tracker expects
            # gps_accuracy in meters.
            gps_accuracy = round(
                convert(float(gps_accuracy), LENGTH_FEET, LENGTH_METERS)
            )
        except (TypeError, ValueError):
            self._err(dev_id, f"GPS data invalid: {lat}, {lon}, {gps_accuracy}")
            return

        self._ok(dev_id)

        msg = f"Updating {dev_id}"
        if prev_seen:
            msg += f"; Time since last update: {last_seen - prev_seen}"
        _LOGGER.debug(msg)

        if self._max_gps_accuracy is not None and gps_accuracy > self._max_gps_accuracy:
            _LOGGER.warning(
                "%s: Ignoring update because expected GPS "
                "accuracy (%.0f) is not met: %.0f",
                dev_id,
                self._max_gps_accuracy,
                gps_accuracy,
            )
            return

        # Get raw attribute data, converting empty strings to None.
        place = loc.get("name") or None
        address1 = loc.get("address1") or None
        address2 = loc.get("address2") or None
        if address1 and address2:
            address = ", ".join([address1, address2])
        else:
            address = address1 or address2
        raw_speed = loc.get("speed") or None
        driving = _bool_attr_from_int(loc.get("isDriving"))
        moving = _bool_attr_from_int(loc.get("inTransit"))
        try:
            battery = int(float(loc.get("battery")))
        except (TypeError, ValueError):
            battery = None

        # Try to convert raw speed into real speed.
        try:
            speed = float(raw_speed) * SPEED_FACTOR_MPH
            if self._hass.config.units.is_metric:
                speed = convert(speed, LENGTH_MILES, LENGTH_KILOMETERS)
            speed = max(0, round(speed))
        except (TypeError, ValueError):
            speed = STATE_UNKNOWN

        # Make driving attribute True if it isn't and we can derive that it
        # should be True from other data.
        if (
            driving in (STATE_UNKNOWN, False)
            and self._driving_speed is not None
            and speed != STATE_UNKNOWN
        ):
            driving = speed >= self._driving_speed

        attrs = {
            ATTR_ADDRESS: address,
            ATTR_AT_LOC_SINCE: _dt_attr_from_ts(loc.get("since")),
            ATTR_BATTERY_CHARGING: _bool_attr_from_int(loc.get("charge")),
            ATTR_DRIVING: driving,
            ATTR_LAST_SEEN: last_seen,
            ATTR_MOVING: moving,
            ATTR_PLACE: place,
            ATTR_RAW_SPEED: raw_speed,
            ATTR_SPEED: speed,
            ATTR_WIFI_ON: _bool_attr_from_int(loc.get("wifiState")),
        }

        # If user wants driving or moving to be shown as state, and current
        # location is not in a HA zone, then set location name accordingly.
        loc_name = None
        active_zone = run_callback_threadsafe(
            self._hass.loop, async_active_zone, self._hass, lat, lon, gps_accuracy
        ).result()
        if not active_zone:
            if SHOW_DRIVING in self._show_as_state and driving is True:
                loc_name = SHOW_DRIVING
            elif SHOW_MOVING in self._show_as_state and moving is True:
                loc_name = SHOW_MOVING

        self._see(
            dev_id=dev_id,
            location_name=loc_name,
            gps=(lat, lon),
            gps_accuracy=gps_accuracy,
            battery=battery,
            attributes=attrs,
            picture=member.get("avatar"),
        )

    def _update_members(self, members, members_updated):
        for member in members:
            member_id = member["id"]
            if member_id in members_updated:
                continue
            err_key = "Member data"
            try:
                first = member.get("firstName")
                last = member.get("lastName")
                if first and last:
                    full_name = " ".join([first, last])
                else:
                    full_name = first or last
                slug_name = cv.slugify(full_name)
                include_member = _include_name(self._members_filter, slug_name)
                dev_id = self._dev_id(slug_name)
                if member_id not in self._members_logged:
                    self._members_logged.add(member_id)
                    _LOGGER.debug(
                        "%s -> %s: will%s be tracked, id=%s",
                        full_name,
                        dev_id,
                        "" if include_member else " NOT",
                        member_id,
                    )
                sharing = bool(int(member["features"]["shareLocation"]))
            except (KeyError, TypeError, ValueError, vol.Invalid):
                self._err(err_key, member)
                continue
            self._ok(err_key)

            if include_member and sharing:
                members_updated.append(member_id)
                self._update_member(member, dev_id)

    def _update_life360(self, now=None):
        circles_updated = []
        members_updated = []

        for api in self._apis.values():
            err_key = "get_circles"
            try:
                circles = api.get_circles()
            except Life360Error as exc:
                self._exc(err_key, exc)
                continue
            self._ok(err_key)

            for circle in circles:
                circle_id = circle["id"]
                if circle_id in circles_updated:
                    continue
                circles_updated.append(circle_id)
                circle_name = circle["name"]
                incl_circle = _include_name(self._circles_filter, circle_name)
                if circle_id not in self._circles_logged:
                    self._circles_logged.add(circle_id)
                    _LOGGER.debug(
                        "%s Circle: will%s be included, id=%s",
                        circle_name,
                        "" if incl_circle else " NOT",
                        circle_id,
                    )
                    try:
                        places = api.get_circle_places(circle_id)
                        place_data = "Circle's Places:"
                        for place in places:
                            place_data += f"\n- name: {place['name']}"
                            place_data += f"\n  latitude: {place['latitude']}"
                            place_data += f"\n  longitude: {place['longitude']}"
                            place_data += f"\n  radius: {place['radius']}"
                        if not places:
                            place_data += " None"
                        _LOGGER.debug(place_data)
                    except (Life360Error, KeyError):
                        pass
                if incl_circle:
                    err_key = f'get_circle_members "{circle_name}"'
                    try:
                        members = api.get_circle_members(circle_id)
                    except Life360Error as exc:
                        self._exc(err_key, exc)
                        continue
                    self._ok(err_key)

                    self._update_members(members, members_updated)
