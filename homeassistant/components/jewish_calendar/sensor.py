"""Support for Jewish calendar sensors."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from hdate import HDateInfo, Zmanim
from hdate.holidays import HolidayDatabase
from hdate.parasha import Parasha

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import SUN_EVENT_SUNSET, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .entity import JewishCalendarConfigEntry, JewishCalendarEntity

_LOGGER = logging.getLogger(__name__)

INFO_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="date",
        name="Date",
        icon="mdi:star-david",
        translation_key="hebrew_date",
    ),
    SensorEntityDescription(
        key="weekly_portion",
        name="Parshat Hashavua",
        icon="mdi:book-open-variant",
        device_class=SensorDeviceClass.ENUM,
    ),
    SensorEntityDescription(
        key="holiday",
        name="Holiday",
        icon="mdi:calendar-star",
        device_class=SensorDeviceClass.ENUM,
    ),
    SensorEntityDescription(
        key="omer_count",
        name="Day of the Omer",
        icon="mdi:counter",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="daf_yomi",
        name="Daf Yomi",
        icon="mdi:book-open-variant",
        entity_registry_enabled_default=False,
    ),
)

TIME_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="alot_hashachar",
        name="Alot Hashachar",  # codespell:ignore alot
        icon="mdi:weather-sunset-up",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="talit_and_tefillin",
        name="Talit and Tefillin",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="netz_hachama",
        name="Hanetz Hachama",
        icon="mdi:calendar-clock",
    ),
    SensorEntityDescription(
        key="sof_zman_shema_gra",
        name='Latest time for Shma Gr"a',
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="sof_zman_shema_mga",
        name='Latest time for Shma MG"A',
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="sof_zman_tfilla_gra",
        name='Latest time for Tefilla Gr"a',
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="sof_zman_tfilla_mga",
        name='Latest time for Tefilla MG"A',
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="chatzot_hayom",
        name="Chatzot Hayom",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="mincha_gedola",
        name="Mincha Gedola",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="mincha_ketana",
        name="Mincha Ketana",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="plag_hamincha",
        name="Plag Hamincha",
        icon="mdi:weather-sunset-down",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="shkia",
        name="Shkia",
        icon="mdi:weather-sunset",
    ),
    SensorEntityDescription(
        key="tset_hakohavim_tsom",
        name="T'set Hakochavim",
        icon="mdi:weather-night",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="tset_hakohavim_shabbat",
        name="T'set Hakochavim, 3 stars",
        icon="mdi:weather-night",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="upcoming_shabbat_candle_lighting",
        name="Upcoming Shabbat Candle Lighting",
        icon="mdi:candle",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="upcoming_shabbat_havdalah",
        name="Upcoming Shabbat Havdalah",
        icon="mdi:weather-night",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="upcoming_candle_lighting",
        name="Upcoming Candle Lighting",
        icon="mdi:candle",
    ),
    SensorEntityDescription(
        key="upcoming_havdalah",
        name="Upcoming Havdalah",
        icon="mdi:weather-night",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JewishCalendarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Jewish calendar sensors ."""
    sensors = [
        JewishCalendarSensor(config_entry, description) for description in INFO_SENSORS
    ]
    sensors.extend(
        JewishCalendarTimeSensor(config_entry, description)
        for description in TIME_SENSORS
    )

    async_add_entities(sensors)


class JewishCalendarSensor(JewishCalendarEntity, SensorEntity):
    """Representation of an Jewish calendar sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        config_entry: JewishCalendarConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Jewish calendar sensor."""
        super().__init__(config_entry, description)
        self._attrs: dict[str, str] = {}

    async def async_update(self) -> None:
        """Update the state of the sensor."""
        now = dt_util.now()
        _LOGGER.debug("Now: %s Location: %r", now, self._location)

        today = now.date()
        event_date = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)

        if event_date is None:
            _LOGGER.error("Can't get sunset event date for %s", today)
            return

        sunset = dt_util.as_local(event_date)

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        daytime_date = HDateInfo(
            today, diaspora=self._diaspora, language=self._language
        )

        # The Jewish day starts after darkness (called "tzais") and finishes at
        # sunset ("shkia"). The time in between is a gray area
        # (aka "Bein Hashmashot"  # codespell:ignore
        # - literally: "in between the sun and the moon").

        # For some sensors, it is more interesting to consider the date to be
        # tomorrow based on sunset ("shkia"), for others based on "tzais".
        # Hence the following variables.
        after_tzais_date = after_shkia_date = daytime_date
        today_times = self.make_zmanim(today)

        if now > sunset:
            after_shkia_date = daytime_date.next_day

        if today_times.havdalah and now > today_times.havdalah:
            after_tzais_date = daytime_date.next_day

        self._attr_native_value = self.get_state(
            daytime_date, after_shkia_date, after_tzais_date
        )
        _LOGGER.debug(
            "New value for %s: %s", self.entity_description.key, self._attr_native_value
        )

    def make_zmanim(self, date: dt.date) -> Zmanim:
        """Create a Zmanim object."""
        return Zmanim(
            date=date,
            location=self._location,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
            language=self._language,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        return self._attrs

    def get_state(
        self,
        daytime_date: HDateInfo,
        after_shkia_date: HDateInfo,
        after_tzais_date: HDateInfo,
    ) -> Any | None:
        """For a given type of sensor, return the state."""
        # Terminology note: by convention in py-libhdate library, "upcoming"
        # refers to "current" or "upcoming" dates.
        if self.entity_description.key == "date":
            hdate = after_shkia_date.hdate
            hdate.month.set_language(self._language)
            self._attrs = {
                "hebrew_year": str(hdate.year),
                "hebrew_month_name": str(hdate.month),
                "hebrew_day": str(hdate.day),
            }
            return after_shkia_date.hdate
        if self.entity_description.key == "weekly_portion":
            self._attr_options = list(Parasha)
            # Compute the weekly portion based on the upcoming shabbat.
            return after_tzais_date.upcoming_shabbat.parasha
        if self.entity_description.key == "holiday":
            _holidays = after_shkia_date.holidays
            _id = ", ".join(holiday.name for holiday in _holidays)
            _type = ", ".join(
                dict.fromkeys(_holiday.type.name for _holiday in _holidays)
            )
            self._attrs = {"id": _id, "type": _type}
            self._attr_options = HolidayDatabase(self._diaspora).get_all_names(
                self._language
            )
            return ", ".join(str(holiday) for holiday in _holidays) if _holidays else ""
        if self.entity_description.key == "omer_count":
            return after_shkia_date.omer.total_days if after_shkia_date.omer else 0
        if self.entity_description.key == "daf_yomi":
            return daytime_date.daf_yomi

        return None


class JewishCalendarTimeSensor(JewishCalendarSensor):
    """Implement attributes for sensors returning times."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def get_state(
        self,
        daytime_date: HDateInfo,
        after_shkia_date: HDateInfo,
        after_tzais_date: HDateInfo,
    ) -> Any | None:
        """For a given type of sensor, return the state."""
        if self.entity_description.key == "upcoming_shabbat_candle_lighting":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat.previous_day.gdate
            )
            return times.candle_lighting
        if self.entity_description.key == "upcoming_candle_lighting":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.first_day.previous_day.gdate
            )
            return times.candle_lighting
        if self.entity_description.key == "upcoming_shabbat_havdalah":
            times = self.make_zmanim(after_tzais_date.upcoming_shabbat.gdate)
            return times.havdalah
        if self.entity_description.key == "upcoming_havdalah":
            times = self.make_zmanim(
                after_tzais_date.upcoming_shabbat_or_yom_tov.last_day.gdate
            )
            return times.havdalah

        times = self.make_zmanim(dt_util.now().date())
        return times.zmanim[self.entity_description.key].local
