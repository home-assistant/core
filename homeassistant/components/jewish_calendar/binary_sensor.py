"""Support for Jewish Calendar binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt

from hdate.zmanim import Zmanim

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import JewishCalendarConfigEntry, JewishCalendarEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True)
class JewishCalendarBinarySensorMixIns(BinarySensorEntityDescription):
    """Binary Sensor description mixin class for Jewish Calendar."""

    is_on: Callable[[Zmanim, dt.datetime], bool] = lambda _, __: False


@dataclass(frozen=True)
class JewishCalendarBinarySensorEntityDescription(
    JewishCalendarBinarySensorMixIns, BinarySensorEntityDescription
):
    """Binary Sensor Entity description for Jewish Calendar."""


BINARY_SENSORS: tuple[JewishCalendarBinarySensorEntityDescription, ...] = (
    JewishCalendarBinarySensorEntityDescription(
        key="issur_melacha_in_effect",
        translation_key="issur_melacha_in_effect",
        is_on=lambda state, now: bool(state.issur_melacha_in_effect(now)),
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="erev_shabbat_hag",
        translation_key="erev_shabbat_hag",
        is_on=lambda state, now: bool(state.erev_shabbat_chag(now)),
        entity_registry_enabled_default=False,
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="motzei_shabbat_hag",
        translation_key="motzei_shabbat_hag",
        is_on=lambda state, now: bool(state.motzei_shabbat_chag(now)),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JewishCalendarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Jewish Calendar binary sensors."""
    async_add_entities(
        JewishCalendarBinarySensor(config_entry, description)
        for description in BINARY_SENSORS
    )


class JewishCalendarBinarySensor(JewishCalendarEntity, BinarySensorEntity):
    """Representation of an Jewish Calendar binary sensor."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _update_unsub: CALLBACK_TYPE | None = None

    entity_description: JewishCalendarBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        zmanim = self.make_zmanim(dt.date.today())
        return self.entity_description.is_on(zmanim, dt_util.now())

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self._schedule_update()

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._update_unsub:
            self._update_unsub()
            self._update_unsub = None
        return await super().async_will_remove_from_hass()

    @callback
    def _update(self, now: dt.datetime | None = None) -> None:
        """Update the state of the sensor."""
        self._update_unsub = None
        self._schedule_update()
        self.async_write_ha_state()

    def _schedule_update(self) -> None:
        """Schedule the next update of the sensor."""
        now = dt_util.now()
        zmanim = self.make_zmanim(dt.date.today())
        update = zmanim.netz_hachama.local + dt.timedelta(days=1)
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
