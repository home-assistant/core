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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import JewishCalendarConfigEntry, JewishCalendarEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class JewishCalendarBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary Sensor Entity description for Jewish Calendar."""

    is_on: Callable[[Zmanim], Callable[[dt.datetime], bool]]


BINARY_SENSORS: tuple[JewishCalendarBinarySensorEntityDescription, ...] = (
    JewishCalendarBinarySensorEntityDescription(
        key="issur_melacha_in_effect",
        translation_key="issur_melacha_in_effect",
        is_on=lambda state: state.issur_melacha_in_effect,
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="erev_shabbat_hag",
        translation_key="erev_shabbat_hag",
        is_on=lambda state: state.erev_shabbat_chag,
        entity_registry_enabled_default=False,
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="motzei_shabbat_hag",
        translation_key="motzei_shabbat_hag",
        is_on=lambda state: state.motzei_shabbat_chag,
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

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    entity_description: JewishCalendarBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if sensor is on."""
        zmanim = self.make_zmanim(dt.date.today())
        return self.entity_description.is_on(zmanim)(dt_util.now())

    def _update_times(self, zmanim: Zmanim) -> list[dt.datetime | None]:
        """Return a list of times to update the sensor."""
        return [
            zmanim.netz_hachama.local + dt.timedelta(days=1),
            zmanim.candle_lighting,
            zmanim.havdalah,
        ]
