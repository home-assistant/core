"""Support for Jewish calendar sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt

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
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import (
    JewishCalendarConfigEntry,
    JewishCalendarDataResults,
    JewishCalendarEntity,
)


@dataclass(frozen=True, kw_only=True)
class JewishCalendarSensorDescription(SensorEntityDescription):
    """Class describing Jewish Calendar sensor entities."""

    value_fn: Callable[[JewishCalendarDataResults], str | int]


@dataclass(frozen=True, kw_only=True)
class JewishCalendarTimestampSensorDescription(SensorEntityDescription):
    """Class describing Jewish Calendar sensor entities."""

    value_fn: (
        Callable[[HDateInfo, Callable[[dt.date], Zmanim]], dt.datetime | None] | None
    ) = None


INFO_SENSORS: tuple[JewishCalendarSensorDescription, ...] = (
    JewishCalendarSensorDescription(
        key="date",
        translation_key="hebrew_date",
        icon="mdi:star-david",
        value_fn=lambda results: str(results.after_shkia_date.hdate),
    ),
    JewishCalendarSensorDescription(
        key="weekly_portion",
        translation_key="weekly_portion",
        icon="mdi:book-open-variant",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda results: results.after_tzais_date.upcoming_shabbat.parasha,
    ),
    JewishCalendarSensorDescription(
        key="holiday",
        translation_key="holiday",
        icon="mdi:calendar-star",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda results: ", ".join(
            str(holiday) for holiday in results.after_shkia_date.holidays
        ),
    ),
    JewishCalendarSensorDescription(
        key="omer_count",
        translation_key="omer_count",
        icon="mdi:counter",
        entity_registry_enabled_default=False,
        value_fn=lambda results: results.after_shkia_date.omer.total_days
        if results.after_shkia_date.omer
        else 0,
    ),
    JewishCalendarSensorDescription(
        key="daf_yomi",
        translation_key="daf_yomi",
        icon="mdi:book-open-variant",
        entity_registry_enabled_default=False,
        value_fn=lambda results: str(results.daytime_date.daf_yomi),
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
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_shabbat_havdalah",
        translation_key="upcoming_shabbat_havdalah",
        icon="mdi:weather-night",
        entity_registry_enabled_default=False,
        value_fn=lambda at_date, mz: mz(at_date.upcoming_shabbat.gdate).havdalah,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_candle_lighting",
        translation_key="upcoming_candle_lighting",
        icon="mdi:candle",
        value_fn=lambda at_date, mz: mz(
            at_date.upcoming_shabbat_or_yom_tov.first_day.previous_day.gdate
        ).candle_lighting,
    ),
    JewishCalendarTimestampSensorDescription(
        key="upcoming_havdalah",
        translation_key="upcoming_havdalah",
        icon="mdi:weather-night",
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
    async_add_entities(
        [
            JewishCalendarSensor(config_entry, description)
            for description in INFO_SENSORS
        ]
    )
    async_add_entities(
        [
            JewishCalendarTimeSensor(config_entry, description)
            for description in TIME_SENSORS
        ]
    )


class JewishCalendarSensor(JewishCalendarEntity, SensorEntity):
    """Representation of an Jewish calendar sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    entity_description: JewishCalendarSensorDescription

    def __init__(
        self, config_entry: JewishCalendarConfigEntry, description: EntityDescription
    ) -> None:
        """Initialize the Jewish calendar sensor."""
        super().__init__(config_entry, description)

        # Set the options for enumeration sensors
        if description.key == "weekly_portion":
            self._attr_options = [str(p) for p in Parasha]
        elif description.key == "holiday":
            self._attr_options = HolidayDatabase(self.data.diaspora).get_all_names()

    @property
    def native_value(self) -> str | int | dt.datetime | None:
        """Return the state of the sensor."""
        if self.data.results is None:
            return None
        return self.entity_description.value_fn(self.data.results)

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        await self.async_update_data()

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return the state attributes."""
        if self.data.results is None:
            return {}
        if self.entity_description.key == "date":
            hdate = self.data.results.after_shkia_date.hdate
            return {
                "hebrew_year": str(hdate.year),
                "hebrew_month_name": str(hdate.month),
                "hebrew_day": str(hdate.day),
            }
        if self.entity_description.key == "holiday":
            _holidays = self.data.results.after_shkia_date.holidays
            _id = ", ".join(holiday.name for holiday in _holidays)
            _type = ", ".join(
                dict.fromkeys(_holiday.type.name for _holiday in _holidays)
            )
            return {"id": _id, "type": _type}
        return {}


class JewishCalendarTimeSensor(JewishCalendarEntity, SensorEntity):
    """Implement attributes for sensors returning times."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
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

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        await self.async_update_data()
