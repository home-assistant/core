"""Support for Jewish calendar sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
import logging

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

from .entity import (
    JewishCalendarConfigEntry,
    JewishCalendarDataResults,
    JewishCalendarEntity,
)

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class JewishCalendarBaseSensorDescription(SensorEntityDescription):
    """Base class describing Jewish Calendar sensor entities."""

    value_fn: Callable | None


@dataclass(frozen=True, kw_only=True)
class JewishCalendarSensorDescription(JewishCalendarBaseSensorDescription):
    """Class describing Jewish Calendar sensor entities."""

    value_fn: Callable[[JewishCalendarDataResults], str | int]
    attr_fn: Callable[[JewishCalendarDataResults], dict[str, str]] | None = None
    options_fn: Callable[[bool], list[str]] | None = None


@dataclass(frozen=True, kw_only=True)
class JewishCalendarTimestampSensorDescription(JewishCalendarBaseSensorDescription):
    """Class describing Jewish Calendar sensor timestamp entities."""

    value_fn: (
        Callable[[HDateInfo, Callable[[dt.date], Zmanim]], dt.datetime | None] | None
    ) = None


INFO_SENSORS: tuple[JewishCalendarSensorDescription, ...] = (
    JewishCalendarSensorDescription(
        key="date",
        translation_key="hebrew_date",
        value_fn=lambda results: str(results.after_shkia_date.hdate),
        attr_fn=lambda results: {
            "hebrew_year": str(results.after_shkia_date.hdate.year),
            "hebrew_month_name": str(results.after_shkia_date.hdate.month),
            "hebrew_day": str(results.after_shkia_date.hdate.day),
        },
    ),
    JewishCalendarSensorDescription(
        key="weekly_portion",
        translation_key="weekly_portion",
        device_class=SensorDeviceClass.ENUM,
        options_fn=lambda _: [str(p) for p in Parasha],
        value_fn=lambda results: results.after_tzais_date.upcoming_shabbat.parasha,
    ),
    JewishCalendarSensorDescription(
        key="holiday",
        translation_key="holiday",
        device_class=SensorDeviceClass.ENUM,
        options_fn=lambda diaspora: HolidayDatabase(diaspora).get_all_names(),
        value_fn=lambda results: ", ".join(
            str(holiday) for holiday in results.after_shkia_date.holidays
        ),
        attr_fn=lambda results: {
            "id": ", ".join(
                holiday.name for holiday in results.after_shkia_date.holidays
            ),
            "type": ", ".join(
                dict.fromkeys(
                    _holiday.type.name for _holiday in results.after_shkia_date.holidays
                )
            ),
        },
    ),
    JewishCalendarSensorDescription(
        key="omer_count",
        translation_key="omer_count",
        entity_registry_enabled_default=False,
        value_fn=lambda results: results.after_shkia_date.omer.total_days,
    ),
    JewishCalendarSensorDescription(
        key="daf_yomi",
        translation_key="daf_yomi",
        entity_registry_enabled_default=False,
        value_fn=lambda results: results.daytime_date.daf_yomi,
    ),
)

TIME_SENSORS: tuple[JewishCalendarTimestampSensorDescription, ...] = (
    JewishCalendarTimestampSensorDescription(
        key="alot_hashachar",
        translation_key="alot_hashachar",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="talit_and_tefillin",
        translation_key="talit_and_tefillin",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="netz_hachama",
        translation_key="netz_hachama",
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_shema_gra",
        translation_key="sof_zman_shema_gra",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_shema_mga",
        translation_key="sof_zman_shema_mga",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_tfilla_gra",
        translation_key="sof_zman_tfilla_gra",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_tfilla_mga",
        translation_key="sof_zman_tfilla_mga",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="chatzot_hayom",
        translation_key="chatzot_hayom",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="mincha_gedola",
        translation_key="mincha_gedola",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="mincha_ketana",
        translation_key="mincha_ketana",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="plag_hamincha",
        translation_key="plag_hamincha",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="shkia",
        translation_key="shkia",
    ),
    JewishCalendarTimestampSensorDescription(
        key="tset_hakohavim_tsom",
        translation_key="tset_hakohavim_tsom",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="tset_hakohavim_shabbat",
        translation_key="tset_hakohavim_shabbat",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_shabbat_candle_lighting",
        translation_key="upcoming_shabbat_candle_lighting",
        entity_registry_enabled_default=False,
        value_fn=lambda at_date, mz: mz(
            at_date.upcoming_shabbat.previous_day.gdate
        ).candle_lighting,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_shabbat_havdalah",
        translation_key="upcoming_shabbat_havdalah",
        entity_registry_enabled_default=False,
        value_fn=lambda at_date, mz: mz(at_date.upcoming_shabbat.gdate).havdalah,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_candle_lighting",
        translation_key="upcoming_candle_lighting",
        value_fn=lambda at_date, mz: mz(
            at_date.upcoming_shabbat_or_yom_tov.first_day.previous_day.gdate
        ).candle_lighting,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_havdalah",
        translation_key="upcoming_havdalah",
        value_fn=lambda at_date, mz: mz(
            at_date.upcoming_shabbat_or_yom_tov.last_day.gdate
        ).havdalah,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JewishCalendarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Jewish calendar sensors ."""
    sensors: list[JewishCalendarBaseSensor] = [
        JewishCalendarSensor(config_entry, description) for description in INFO_SENSORS
    ]
    sensors.extend(
        JewishCalendarTimeSensor(config_entry, description)
        for description in TIME_SENSORS
    )
    async_add_entities(sensors, update_before_add=True)


class JewishCalendarBaseSensor(JewishCalendarEntity, SensorEntity):
    """Base class for Jewish calendar sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_update(self) -> None:
        """Update the state of the sensor."""
        now = dt_util.now()
        _LOGGER.debug("Now: %s Location: %r", now, self.data.location)

        today = now.date()
        event_date = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, today)

        if event_date is None:
            _LOGGER.error("Can't get sunset event date for %s", today)
            return

        sunset = dt_util.as_local(event_date)

        _LOGGER.debug("Now: %s Sunset: %s", now, sunset)

        daytime_date = HDateInfo(today, diaspora=self.data.diaspora)

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

        self.data.results = JewishCalendarDataResults(
            daytime_date, after_shkia_date, after_tzais_date, today_times
        )


class JewishCalendarSensor(JewishCalendarBaseSensor):
    """Representation of an Jewish calendar sensor."""

    entity_description: JewishCalendarSensorDescription

    def __init__(
        self,
        config_entry: JewishCalendarConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Jewish calendar sensor."""
        super().__init__(config_entry, description)
        # Set the options for enumeration sensors
        if self.entity_description.options_fn is not None:
            self._attr_options = self.entity_description.options_fn(self.data.diaspora)

    @property
    def native_value(self) -> str | int | dt.datetime | None:
        """Return the state of the sensor."""
        if self.data.results is None:
            return None
        return self.entity_description.value_fn(self.data.results)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        if self.data.results is None:
            return {}
        if self.entity_description.attr_fn is not None:
            return self.entity_description.attr_fn(self.data.results)
        return {}


class JewishCalendarTimeSensor(JewishCalendarBaseSensor):
    """Implement attributes for sensors returning times."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    entity_description: JewishCalendarTimestampSensorDescription

    @property
    def native_value(self) -> dt.datetime | None:
        """Return the state of the sensor."""
        if self.data.results is None:
            return None
        if self.entity_description.value_fn is None:
            return self.data.results.zmanim.zmanim[self.entity_description.key].local
        return self.entity_description.value_fn(
            self.data.results.after_tzais_date, self.make_zmanim
        )
