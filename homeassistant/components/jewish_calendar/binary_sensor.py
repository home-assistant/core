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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .entity import JewishCalendarConfigEntry, JewishCalendarEntity


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
        name="Issur Melacha in Effect",
        icon="mdi:power-plug-off",
        is_on=lambda state, now: bool(state.issur_melacha_in_effect(now)),
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="erev_shabbat_hag",
        name="Erev Shabbat/Hag",
        is_on=lambda state, now: bool(state.erev_shabbat_chag(now)),
        entity_registry_enabled_default=False,
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="motzei_shabbat_hag",
        name="Motzei Shabbat/Hag",
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
        zmanim = self.coordinator.data.make_zmanim()
        return self.entity_description.is_on(zmanim, dt_util.now())
