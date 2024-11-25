"""Support for Jewish Calendar binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime as dt
from datetime import datetime

import hdate
from hdate.zmanim import Zmanim

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .entity import JewishCalendarConfigEntry, JewishCalendarEntity


@dataclass(frozen=True)
class JewishCalendarBinarySensorMixIns(BinarySensorEntityDescription):
    """Binary Sensor description mixin class for Jewish Calendar."""

    is_on: Callable[[Zmanim], bool] = lambda _: False


@dataclass(frozen=True)
class JewishCalendarBinarySensorEntityDescription(
    JewishCalendarBinarySensorMixIns, BinarySensorEntityDescription
):
    """Binary Sensor Entity description for Jewish Calendar."""


BINARY_SENSORS: tuple[JewishCalendarBinarySensorEntityDescription, ...] = (
    JewishCalendarBinarySensorEntityDescription(
        key="issur_melacha_in_effect",
        name="Issur Melacha in Effect",
        icon="mdi:power-plug-off",
        is_on=lambda state: bool(state.issur_melacha_in_effect),
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="erev_shabbat_hag",
        name="Erev Shabbat/Hag",
        is_on=lambda state: bool(state.erev_shabbat_chag),
        entity_registry_enabled_default=False,
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="motzei_shabbat_hag",
        name="Motzei Shabbat/Hag",
        is_on=lambda state: bool(state.motzei_shabbat_chag),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JewishCalendarConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
        zmanim = self._get_zmanim()
        return self.entity_description.is_on(zmanim)

    def _get_zmanim(self) -> Zmanim:
        """Return the Zmanim object for now()."""
        return hdate.Zmanim(
            date=dt_util.now(),
            location=self._location,
            candle_lighting_offset=self._candle_lighting_offset,
            havdalah_offset=self._havdalah_offset,
            hebrew=self._hebrew,
        )

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
    def _update(self, now: datetime | None = None) -> None:
        """Update the state of the sensor."""
        self._update_unsub = None
        self._schedule_update()
        self.async_write_ha_state()

    def _schedule_update(self) -> None:
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
