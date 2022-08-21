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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import event
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import DOMAIN


@dataclass
class JewishCalendarBinarySensorMixIns(BinarySensorEntityDescription):
    """Binary Sensor description mixin class for Jewish Calendar."""

    is_on: Callable[..., bool] = lambda _: False


@dataclass
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
        is_on=lambda state: bool(state.erev_shabbat_hag),
    ),
    JewishCalendarBinarySensorEntityDescription(
        key="motzei_shabbat_hag",
        name="Motzei Shabbat/Hag",
        is_on=lambda state: bool(state.motzei_shabbat_hag),
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Jewish Calendar binary sensor devices."""
    if discovery_info is None:
        return

    async_add_entities(
        [
            JewishCalendarBinarySensor(hass.data[DOMAIN], description)
            for description in BINARY_SENSORS
        ]
    )


class JewishCalendarBinarySensor(BinarySensorEntity):
    """Representation of an Jewish Calendar binary sensor."""

    _attr_should_poll = False
    entity_description: JewishCalendarBinarySensorEntityDescription

    def __init__(
        self,
        data: dict[str, str | bool | int | float],
        description: JewishCalendarBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        self.entity_description = description
        self._attr_name = f"{data['name']} {description.name}"
        self._attr_unique_id = f"{data['prefix']}_{description.key}"
        self._location = data["location"]
        self._hebrew = data["language"] == "hebrew"
        self._candle_lighting_offset = data["candle_lighting_offset"]
        self._havdalah_offset = data["havdalah_offset"]
        self._update_unsub: CALLBACK_TYPE | None = None

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
