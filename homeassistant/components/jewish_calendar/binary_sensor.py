"""Support for Jewish Calendar binary sensors."""
import datetime as dt

import hdate

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers import event
import homeassistant.util.dt as dt_util

from . import DOMAIN, SENSOR_TYPES


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Jewish Calendar binary sensor devices."""
    if discovery_info is None:
        return

    async_add_entities(
        [
            JewishCalendarBinarySensor(hass.data[DOMAIN], sensor, sensor_info)
            for sensor, sensor_info in SENSOR_TYPES["binary"].items()
        ]
    )


class JewishCalendarBinarySensor(BinarySensorEntity):
    """Representation of an Jewish Calendar binary sensor."""

    def __init__(self, data, sensor, sensor_info):
        """Initialize the binary sensor."""
        self._location = data["location"]
        self._type = sensor
        self._name = f"{data['name']} {sensor_info[0]}"
        self._icon = sensor_info[1]
        self._hebrew = data["language"] == "hebrew"
        self._candle_lighting_offset = data["candle_lighting_offset"]
        self._havdalah_offset = data["havdalah_offset"]
        self._prefix = data["prefix"]
        self._update_unsub = None

    @property
    def icon(self):
        """Return the icon of the entity."""
        return self._icon

    @property
    def unique_id(self) -> str:
        """Generate a unique id."""
        return f"{self._prefix}_{self._type}"

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._get_zmanim().issur_melacha_in_effect

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    def _get_zmanim(self):
        """Return the Zmanim object for now()."""
        return hdate.Zmanim(
            date=dt_util.now(),
            location=self._location,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
            hebrew=self._hebrew,
        )

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._schedule_update()

    @callback
    def _update(self, now=None):
        """Update the state of the sensor."""
        self._update_unsub = None
        self._schedule_update()
        self.async_write_ha_state()

    def _schedule_update(self):
        """Schedule the next update of the sensor."""
        now = dt_util.now()
        zmanim = self._get_zmanim()
        update = zmanim.zmanim["sunrise"] + dt.timedelta(days=1)
        candle_lighting = zmanim.candle_lighting
        if candle_lighting is not None and now < candle_lighting < update:
            update = candle_lighting
        havdalah = zmanim.havdalah
        if havdalah is not None and now < havdalah < update:
            update = havdalah
        if self._update_unsub:
            self._update_unsub()
        self._update_unsub = event.async_track_point_in_time(
            self.hass, self._update, update
        )
