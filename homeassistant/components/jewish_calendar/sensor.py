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
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
import homeassistant.util.dt as dt_util

from .entity import JewishCalendarConfigEntry, JewishCalendarEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class JewishCalendarBaseSensorDescription(SensorEntityDescription):
    """Base class describing Jewish Calendar sensor entities."""

    value_fn: Callable | None
    next_update_fn: Callable[[Zmanim], dt.datetime | None] | None


@dataclass(frozen=True, kw_only=True)
class JewishCalendarSensorDescription(JewishCalendarBaseSensorDescription):
    """Class describing Jewish Calendar sensor entities."""

    value_fn: Callable[[HDateInfo], str | int]
    attr_fn: Callable[[HDateInfo], dict[str, str]] | None = None
    options_fn: Callable[[bool], list[str]] | None = None
    next_update_fn: Callable[[Zmanim], dt.datetime | None] | None = (
        lambda zmanim: zmanim.shkia.local
    )


@dataclass(frozen=True, kw_only=True)
class JewishCalendarTimestampSensorDescription(JewishCalendarBaseSensorDescription):
    """Class describing Jewish Calendar sensor timestamp entities."""

    value_fn: (
        Callable[[HDateInfo, Callable[[dt.date], Zmanim]], dt.datetime | None] | None
    ) = None
    next_update_fn: Callable[[Zmanim], dt.datetime | None] | None = None


INFO_SENSORS: tuple[JewishCalendarSensorDescription, ...] = (
    JewishCalendarSensorDescription(
        key="date",
        translation_key="hebrew_date",
        icon="mdi:star-david",
        value_fn=lambda info: str(info.hdate),
        attr_fn=lambda info: {
            "hebrew_year": str(info.hdate.year),
            "hebrew_month_name": str(info.hdate.month),
            "hebrew_day": str(info.hdate.day),
        },
    ),
    JewishCalendarSensorDescription(
        key="weekly_portion",
        translation_key="weekly_portion",
        icon="mdi:book-open-variant",
        device_class=SensorDeviceClass.ENUM,
        options_fn=lambda _: [str(p) for p in Parasha],
        value_fn=lambda info: str(info.upcoming_shabbat.parasha),
        next_update_fn=lambda zmanim: zmanim.havdalah,
    ),
    JewishCalendarSensorDescription(
        key="holiday",
        translation_key="holiday",
        icon="mdi:calendar-star",
        device_class=SensorDeviceClass.ENUM,
        options_fn=lambda diaspora: HolidayDatabase(diaspora).get_all_names(),
        value_fn=lambda info: ", ".join(str(holiday) for holiday in info.holidays),
        attr_fn=lambda info: {
            "id": ", ".join(holiday.name for holiday in info.holidays),
            "type": ", ".join(
                dict.fromkeys(_holiday.type.name for _holiday in info.holidays)
            ),
        },
    ),
    JewishCalendarSensorDescription(
        key="omer_count",
        translation_key="omer_count",
        icon="mdi:counter",
        entity_registry_enabled_default=False,
        value_fn=lambda info: info.omer.total_days if info.omer else 0,
    ),
    JewishCalendarSensorDescription(
        key="daf_yomi",
        translation_key="daf_yomi",
        icon="mdi:book-open-variant",
        entity_registry_enabled_default=False,
        value_fn=lambda info: str(info.daf_yomi),
    ),
)

TIME_SENSORS: tuple[JewishCalendarTimestampSensorDescription, ...] = (
    JewishCalendarTimestampSensorDescription(
        key="alot_hashachar",
        translation_key="alot_hashachar",
        icon="mdi:weather-sunset-up",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="talit_and_tefillin",
        translation_key="talit_and_tefillin",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="netz_hachama",
        translation_key="netz_hachama",
        icon="mdi:calendar-clock",
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_shema_gra",
        translation_key="sof_zman_shema_gra",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_shema_mga",
        translation_key="sof_zman_shema_mga",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_tfilla_gra",
        translation_key="sof_zman_tfilla_gra",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="sof_zman_tfilla_mga",
        translation_key="sof_zman_tfilla_mga",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="chatzot_hayom",
        translation_key="chatzot_hayom",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="mincha_gedola",
        translation_key="mincha_gedola",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="mincha_ketana",
        translation_key="mincha_ketana",
        icon="mdi:calendar-clock",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="plag_hamincha",
        translation_key="plag_hamincha",
        icon="mdi:weather-sunset-down",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="shkia",
        translation_key="shkia",
        icon="mdi:weather-sunset",
    ),
    JewishCalendarTimestampSensorDescription(
        key="tset_hakohavim_tsom",
        translation_key="tset_hakohavim_tsom",
        icon="mdi:weather-night",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="tset_hakohavim_shabbat",
        translation_key="tset_hakohavim_shabbat",
        icon="mdi:weather-night",
        entity_registry_enabled_default=False,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_shabbat_candle_lighting",
        translation_key="upcoming_shabbat_candle_lighting",
        icon="mdi:candle",
        entity_registry_enabled_default=False,
        value_fn=lambda at_date, mz: mz(
            at_date.upcoming_shabbat.previous_day.gdate
        ).candle_lighting,
        next_update_fn=lambda zmanim: zmanim.havdalah,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_shabbat_havdalah",
        translation_key="upcoming_shabbat_havdalah",
        icon="mdi:weather-night",
        entity_registry_enabled_default=False,
        value_fn=lambda at_date, mz: mz(at_date.upcoming_shabbat.gdate).havdalah,
        next_update_fn=lambda zmanim: zmanim.havdalah,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_candle_lighting",
        translation_key="upcoming_candle_lighting",
        icon="mdi:candle",
        value_fn=lambda at_date, mz: mz(
            at_date.upcoming_shabbat_or_yom_tov.first_day.previous_day.gdate
        ).candle_lighting,
        next_update_fn=lambda zmanim: zmanim.havdalah,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_havdalah",
        translation_key="upcoming_havdalah",
        icon="mdi:weather-night",
        value_fn=lambda at_date, mz: mz(
            at_date.upcoming_shabbat_or_yom_tov.last_day.gdate
        ).havdalah,
        next_update_fn=lambda zmanim: zmanim.havdalah,
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
    async_add_entities(sensors)


class JewishCalendarBaseSensor(JewishCalendarEntity, SensorEntity):
    """Base class for Jewish calendar sensors."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    entity_description: JewishCalendarBaseSensorDescription

    def get_dateinfo(self, now: dt.datetime | None = None) -> HDateInfo:
        """Get the next date info."""
        if now is None:
            now = dt_util.now()

        today = now.date()
        assert self.coordinator.data.results is not None, "Data not available"
        zmanim = self.coordinator.data.results.zmanim
        update = None
        if self.entity_description.next_update_fn:
            update = self.entity_description.next_update_fn(zmanim)

        _LOGGER.debug("Today: %s, update: %s", today, update)
        if update is not None and now >= update:
            return self.coordinator.data.results.dateinfo.next_day
        return self.coordinator.data.results.dateinfo


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
            self._attr_options = self.entity_description.options_fn(
                self.coordinator.data.diaspora
            )

    @property
    def native_value(self) -> str | int | dt.datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.get_dateinfo())

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        if self.entity_description.attr_fn is None:
            return {}
        return self.entity_description.attr_fn(self.get_dateinfo())


class JewishCalendarTimeSensor(JewishCalendarBaseSensor):
    """Implement attributes for sensors returning times."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    entity_description: JewishCalendarTimestampSensorDescription

    @property
    def native_value(self) -> dt.datetime | None:
        """Return the state of the sensor."""
        assert self.coordinator.data.results is not None, "Data not available"
        if self.entity_description.value_fn is None:
            return self.coordinator.data.results.zmanim.zmanim[
                self.entity_description.key
            ].local
        return self.entity_description.value_fn(
            self.get_dateinfo(), self.coordinator.make_zmanim
        )
