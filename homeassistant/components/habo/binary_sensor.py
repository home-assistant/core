"""The Mawaqit binary sensor to add entities in Home Assistant."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util

from .const import DOMAIN, SENSOR_TYPES
from .mawaqit_hub import MawaqitHub

_LOGGER = logging.getLogger(__name__)


def convert_to_time(ts, return_utc=False):
    """Convert prayertime to UTC datetimestamp."""
    local_time_prayer = dt_util.parse_time(ts)
    local_datetime_prayer = dt_util.now().replace(
        hour=local_time_prayer.hour,
        minute=local_time_prayer.minute,
        second=0,
        microsecond=0,
    )

    if return_utc:
        return dt_util.as_utc(local_datetime_prayer).astimezone().isoformat()
    else:
        return local_datetime_prayer.isoformat()


def diff_time(ts1, ts2):
    """Return difference in seconds."""
    try:
        if isinstance(ts1, str):
            ts1 = dt_util.parse_datetime(ts1)
        if isinstance(ts2, str):
            ts2 = dt_util.parse_datetime(ts2)
    except Exception:
        raise InvalidEntityFormatError

    if ts1 >= ts2:
        return int((ts1 - ts2).total_seconds())
    else:
        return int((ts2 - ts1).total_seconds())


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up Mawaqit Prayer Time from a config entry."""
    _LOGGER.debug(
        "Saved prayer_data from __init__: %s", hass.data[DOMAIN][entry.entry_id]
    )

    mawaqit_connect = MawaqitHub(
        entry.data["username"],
        entry.data["password"],
        entry.data["latitude"],
        entry.data["longitude"],
        entry.data["uuid"],
        entry.data["token"],
    )

    try:
        last_attempt = dt_util.utcnow()
        await hass.async_add_executor_job(mawaqit_connect.validate_auth)
        prayer_data = await hass.async_add_executor_job(
            mawaqit_connect.get_prayer_times
        )
        last_updated = dt_util.utcnow()
    except Exception:
        raise InvalidEntityFormatError
    else:
        last_attempt = dt_util.utcnow()

    for sensor in SENSOR_TYPES:
        async_add_entities(
            [
                PraySensor(
                    sensor,
                    prayer_data[sensor],
                    SENSOR_TYPES[sensor],
                    entry.data["slug"],
                    last_attempt,
                    last_updated,
                    mawaqit_connect,
                )
            ]
        )

    return True
    # setup_platform


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    add_entities([PraySensor()])


class PraySensor(BinarySensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self,
        prayer_name,
        prayer_time,
        prayer_type,
        mosque_name,
        last_attempt,
        last_updated,
        mawaqit_connect,
    ):
        """Initialize the sensor."""
        self._state = False
        self._prayer_name = prayer_name
        self._prayer_time = prayer_time
        self._prayer_type = prayer_type
        self._mosque_name = mosque_name
        self._last_attempt = last_attempt
        self._last_updated = last_updated
        self._mawaqit_connect = mawaqit_connect

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._prayer_name

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return self._prayer_name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""

        attributes = {
            "mosque": self._mosque_name,
            "prayer": self._prayer_time,
            "prayer_local": convert_to_time(self._prayer_time),
            "prayer_utc": convert_to_time(self._prayer_time, True),
            "last_attempt": self._last_attempt,
            "last_updated": self._last_updated,
        }

        return attributes

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        self.update_prayer_time()
        time_now = dt_util.now().replace(second=0, microsecond=0).isoformat()
        _LOGGER.debug(
            "Time now %s vs Time prayer %s",
            time_now,
            convert_to_time(self._prayer_time),
        )
        self._state = time_now == convert_to_time(self._prayer_time)
        return self._state

    def update_prayer_time(self):
        """Fetch latest prayer time."""
        if dt_util.now().hour == 0 and dt_util.now().minute == 0:
            self._last_attempt = dt_util.utcnow().isoformat()
            self._prayer_time = self._mawaqit_connect.get_prayer_times()[
                self._prayer_name
            ]
            self._last_updated = dt_util.utcnow().isoformat()
        elif diff_time(self._last_attempt, dt_util.utcnow()) > 864000:
            _LOGGER.error(
                "Prayer times have not been retrieved for over %i seconds",
                diff_time(self._last_attempt, dt_util.utcnow()),
            )
        elif diff_time(self._last_attempt, dt_util.utcnow()) > 86400:
            self._last_attempt = dt_util.utcnow().isoformat()
            self._prayer_time = self._mawaqit_connect.get_prayer_times()[
                self._prayer_name
            ]
            self._last_updated = dt_util.utcnow().isoformat()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidEntityFormatError(HomeAssistantError):
    """When an invalid formatted entity is encountered."""
