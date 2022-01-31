"""Support for Jewish Calendar binary sensors."""
from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import cast

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

BINARY_SENSORS = BinarySensorEntityDescription(
    key="issur_melacha_in_effect",
    name="Issur Melacha in Effect",
    icon="mdi:power-plug-off",
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

    async_add_entities([JewishCalendarBinarySensor(hass.data[DOMAIN], BINARY_SENSORS)])


class JewishCalendarBinarySensor(BinarySensorEntity):
    """Representation of an Jewish Calendar binary sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        data: dict[str, str | bool | int | float],
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
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
        return cast(bool, self._get_zmanim().issur_melacha_in_effect)

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
