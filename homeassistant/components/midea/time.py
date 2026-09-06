"""Time platform for Midea."""

from datetime import time
from typing import cast, override

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .entity import MideaConfigEntry, MideaDevice, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0

TIMES: list[TimeEntityDescription] = [
    TimeEntityDescription(
        key="timing_regeneration", translation_key="timing_regeneration"
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up times for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaTime(device, description)
        for description in TIMES
        if f"{description.key}_hour" in device.attributes
        and f"{description.key}_min" in device.attributes
    )


class MideaTime(MideaEntity, TimeEntity):
    """Represent a Midea time entity."""

    entity_description: TimeEntityDescription

    def __init__(
        self, device: MideaDevice, entity_description: TimeEntityDescription
    ) -> None:
        """Midea time entity init."""
        super().__init__(device, entity_description)
        self._hour_attr = f"{entity_description.key}_hour"
        self._min_attr = f"{entity_description.key}_min"

    @property
    @override
    def native_value(self) -> time | None:
        """Native value of the entity."""
        hour = self._device.get_attribute(self._hour_attr)
        minute = self._device.get_attribute(self._min_attr)
        if hour is None or minute is None:
            return None
        try:
            return time(hour=cast("int", hour), minute=cast("int", minute))
        except TypeError, ValueError:
            LOGGER.warning(
                "Invalid time value for %s: hour=%s, minute=%s",
                self.entity_id,
                hour,
                minute,
            )
            return None

    @override
    def set_value(self, value: time) -> None:
        """Set entity value."""
        with midea_api_call():
            self._device.set_attribute(self._hour_attr, value.hour)
            self._device.set_attribute(self._min_attr, value.minute)
