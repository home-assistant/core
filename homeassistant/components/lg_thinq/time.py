"""Support for time entities."""

from __future__ import annotations

from datetime import time
import logging

from thinqconnect import DeviceType
from thinqconnect.integration import TimerProperty

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity

TIMER_ABSOLUTE_TO_START_TIME_DESC = TimeEntityDescription(
    key=TimerProperty.ABSOLUTE_TO_START,
    translation_key=TimerProperty.ABSOLUTE_TO_START,
)
TIMER_ABSOLUTE_TO_STOP_TIME_DESC = TimeEntityDescription(
    key=TimerProperty.ABSOLUTE_TO_STOP,
    translation_key=TimerProperty.ABSOLUTE_TO_STOP,
)

DEVICE_TYPE_TIME_MAP: dict[DeviceType, tuple[TimeEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        TIMER_ABSOLUTE_TO_START_TIME_DESC,
        TIMER_ABSOLUTE_TO_STOP_TIME_DESC,
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        TIMER_ABSOLUTE_TO_START_TIME_DESC,
        TIMER_ABSOLUTE_TO_STOP_TIME_DESC,
    ),
    DeviceType.AIR_PURIFIER: (
        TIMER_ABSOLUTE_TO_START_TIME_DESC,
        TIMER_ABSOLUTE_TO_STOP_TIME_DESC,
    ),
    DeviceType.HUMIDIFIER: (
        TIMER_ABSOLUTE_TO_START_TIME_DESC,
        TIMER_ABSOLUTE_TO_STOP_TIME_DESC,
    ),
    DeviceType.ROBOT_CLEANER: (TIMER_ABSOLUTE_TO_START_TIME_DESC,),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for time platform."""
    entities: list[TimeEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_TIME_MAP.get(coordinator.api.device.device_type)
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQTimeEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(description.key)
                )

    if entities:
        async_add_entities(entities)


class ThinQTimeEntity(ThinQEntity, TimeEntity):
    """Represent a thinq time platform."""

    entity_description: TimeEntityDescription

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()
        if (time_value := self.data.value) is not None:
            self._attr_native_value = (
                time_value
                if isinstance(time_value, time)
                else time.fromisoformat(time_value)
            )
        else:
            self._attr_native_value = None

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.native_value,
        )

    async def async_set_value(self, value: time) -> None:
        """Set the time value."""
        _LOGGER.debug(
            "[%s:%s] async_set_value: %s",
            self.coordinator.device_name,
            self.property_id,
            value,
        )
        await self.async_call_api(self.coordinator.api.post(self.property_id, value))
