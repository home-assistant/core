"""Sensors for the MAWAQIT integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import override

from mawaqit.prayer_times import Prayer, PrayerDay, next_prayer, prayer_day
from mawaqit.types import PrayerTimes

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_UUID
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import MawaqitConfigEntry, MawaqitCoordinator, MawaqitData

PARALLEL_UPDATES = 0

FRIDAY = 4


def _at(prayer: Prayer | None) -> datetime | None:
    return prayer.at if prayer else None


def _iqama(prayer: Prayer | None) -> datetime | None:
    return prayer.iqama if prayer else None


def _jumua(index: int) -> Callable[[PrayerDay], datetime | None]:
    return lambda day: day.jumua[index].at if len(day.jumua) > index else None


def _has_iqama(prayer_times: PrayerTimes) -> bool:
    return prayer_times.iqama_enabled and bool(prayer_times.iqama_calendar)


def _has_jumua(index: int) -> Callable[[PrayerTimes], bool]:
    def has_jumua(prayer_times: PrayerTimes) -> bool:
        first = prayer_times.jumua_as_duhr or prayer_times.jumua
        times = (first, prayer_times.jumua_2, prayer_times.jumua_3)
        return sum(map(bool, times)) > index

    return has_jumua


@dataclass(frozen=True, kw_only=True)
class MawaqitDaySensorEntityDescription(SensorEntityDescription):
    """Describes a time of the prayer day shown by the sensors."""

    device_class: SensorDeviceClass = SensorDeviceClass.TIMESTAMP
    value_fn: Callable[[PrayerDay], datetime | None]
    exists_fn: Callable[[PrayerTimes], bool] = lambda _: True
    # Read the next Friday from the shown day, rather than the shown day.
    friday: bool = False


@dataclass(frozen=True, kw_only=True)
class MawaqitNextPrayerSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor of the next prayer."""

    value_fn: Callable[[Prayer], str | datetime]


DAY_SENSORS: tuple[MawaqitDaySensorEntityDescription, ...] = (
    MawaqitDaySensorEntityDescription(
        key="fajr", translation_key="prayer_fajr", value_fn=lambda day: _at(day.fajr)
    ),
    MawaqitDaySensorEntityDescription(
        key="shuruq",
        translation_key="prayer_shuruq",
        value_fn=lambda day: _at(day.shuruq),
    ),
    MawaqitDaySensorEntityDescription(
        key="dhuhr",
        translation_key="prayer_dhuhr",
        value_fn=lambda day: _at(day.dhuhr),
    ),
    MawaqitDaySensorEntityDescription(
        key="asr", translation_key="prayer_asr", value_fn=lambda day: _at(day.asr)
    ),
    MawaqitDaySensorEntityDescription(
        key="maghrib",
        translation_key="prayer_maghrib",
        value_fn=lambda day: _at(day.maghrib),
    ),
    MawaqitDaySensorEntityDescription(
        key="isha", translation_key="prayer_isha", value_fn=lambda day: _at(day.isha)
    ),
    *(
        MawaqitDaySensorEntityDescription(
            key=key,
            translation_key=f"prayer_{key}",
            value_fn=_jumua(index),
            exists_fn=_has_jumua(index),
            friday=True,
        )
        for index, key in enumerate(("jumua", "jumua_2", "jumua_3"))
    ),
    MawaqitDaySensorEntityDescription(
        key="fajr_iqama",
        translation_key="iqama_fajr",
        value_fn=lambda day: _iqama(day.fajr),
        exists_fn=_has_iqama,
    ),
    MawaqitDaySensorEntityDescription(
        key="dhuhr_iqama",
        translation_key="iqama_dhuhr",
        value_fn=lambda day: _iqama(day.dhuhr),
        exists_fn=_has_iqama,
    ),
    MawaqitDaySensorEntityDescription(
        key="asr_iqama",
        translation_key="iqama_asr",
        value_fn=lambda day: _iqama(day.asr),
        exists_fn=_has_iqama,
    ),
    MawaqitDaySensorEntityDescription(
        key="maghrib_iqama",
        translation_key="iqama_maghrib",
        value_fn=lambda day: _iqama(day.maghrib),
        exists_fn=_has_iqama,
    ),
    MawaqitDaySensorEntityDescription(
        key="isha_iqama",
        translation_key="iqama_isha",
        value_fn=lambda day: _iqama(day.isha),
        exists_fn=_has_iqama,
    ),
)

NEXT_PRAYER_SENSORS: tuple[MawaqitNextPrayerSensorEntityDescription, ...] = (
    MawaqitNextPrayerSensorEntityDescription(
        key="next_salat_name",
        translation_key="next_salat_name",
        device_class=SensorDeviceClass.ENUM,
        options=["fajr", "dhuhr", "jumua", "asr", "maghrib", "isha"],
        value_fn=lambda prayer: prayer.name,
    ),
    MawaqitNextPrayerSensorEntityDescription(
        key="next_salat_time",
        translation_key="next_salat_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda prayer: prayer.at,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MawaqitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the MAWAQIT sensors."""
    coordinator = entry.runtime_data
    prayer_times = coordinator.data.prayer_times
    async_add_entities(
        [
            *(
                MawaqitDaySensor(coordinator, description)
                for description in DAY_SENSORS
                if description.exists_fn(prayer_times)
            ),
            *(
                MawaqitNextPrayerSensor(coordinator, description)
                for description in NEXT_PRAYER_SENSORS
            ),
        ]
    )


def _day_end(data: MawaqitData, day: date) -> datetime:
    """Return when the sensors move from a day to the next one.

    Halfway between its Isha and the next Fajr, so that an Isha after midnight is
    shown until it has passed. At midnight without these times.
    """
    today = prayer_day(data.prayer_times, day, timezone=data.timezone)
    tomorrow = prayer_day(
        data.prayer_times, day + timedelta(days=1), timezone=data.timezone
    )
    if today and today.isha and tomorrow and tomorrow.fajr:
        # In UTC: datetimes of the same time zone subtract in wall-clock time.
        isha = dt_util.as_utc(today.isha.at)
        return isha + (dt_util.as_utc(tomorrow.fajr.at) - isha) / 2
    return datetime.combine(day + timedelta(days=1), time(), data.timezone)


class MawaqitSensor[DescriptionT: SensorEntityDescription](
    CoordinatorEntity[MawaqitCoordinator], SensorEntity
):
    """A sensor whose value also changes at a given time, without new data."""

    _attr_has_entity_name = True
    entity_description: DescriptionT
    _unsub_refresh: CALLBACK_TYPE | None = None

    def __init__(
        self, coordinator: MawaqitCoordinator, description: DescriptionT
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.config_entry.data[CONF_UUID]}_{description.key}"
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Compute the value and schedule its next change."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_refresh)
        self._update_value()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._update_value()
        super()._handle_coordinator_update()

    @callback
    def _refresh(self, _now: datetime) -> None:
        self._unsub_refresh = None
        self._update_value()
        self.async_write_ha_state()

    @callback
    def _cancel_refresh(self) -> None:
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

    @callback
    def _update_value(self) -> None:
        self._cancel_refresh()
        self._attr_native_value, refresh_at = self._compute(
            self.coordinator.data, dt_util.utcnow()
        )
        if refresh_at:
            self._unsub_refresh = async_track_point_in_utc_time(
                self.hass, self._refresh, refresh_at
            )

    def _compute(
        self, data: MawaqitData, now: datetime
    ) -> tuple[str | datetime | None, datetime | None]:
        """Return the value at `now`, and when it changes."""
        raise NotImplementedError


class MawaqitDaySensor(MawaqitSensor[MawaqitDaySensorEntityDescription]):
    """A time of the prayer day: today's, or yesterday's until the night is half over."""

    @override
    def _compute(
        self, data: MawaqitData, now: datetime
    ) -> tuple[datetime | None, datetime]:
        day = now.astimezone(data.timezone).date() - timedelta(days=1)
        while (day_end := _day_end(data, day)) <= now:
            day += timedelta(days=1)
        if self.entity_description.friday:
            day += timedelta(days=(FRIDAY - day.weekday()) % 7)
        prayers = prayer_day(data.prayer_times, day, timezone=data.timezone)
        return (self.entity_description.value_fn(prayers) if prayers else None), day_end


class MawaqitNextPrayerSensor(MawaqitSensor[MawaqitNextPrayerSensorEntityDescription]):
    """The next prayer: Jumua instead of Dhuhr on Fridays."""

    @override
    def _compute(
        self, data: MawaqitData, now: datetime
    ) -> tuple[str | datetime | None, datetime | None]:
        prayer = next_prayer(data.prayer_times, now, timezone=data.timezone)
        if prayer is None:
            return None, None
        return self.entity_description.value_fn(prayer), prayer.at
