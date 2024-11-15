"""Support for button entities."""

from __future__ import annotations

import logging

from thinqconnect import DeviceType
from thinqconnect.integration import TimerProperty

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity

TIMER_ABSOLUTE_TO_START_BUTTON_DESC = ButtonEntityDescription(
    key=TimerProperty.ABSOLUTE_TO_START,
    translation_key="unset_absolute_to_start",
)
TIMER_ABSOLUTE_TO_STOP_BUTTON_DESC = ButtonEntityDescription(
    key=TimerProperty.ABSOLUTE_TO_STOP,
    translation_key="unset_absolute_to_stop",
)

DEVICE_TYPE_BUTTON_MAP: dict[DeviceType, tuple[ButtonEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        TIMER_ABSOLUTE_TO_START_BUTTON_DESC,
        TIMER_ABSOLUTE_TO_STOP_BUTTON_DESC,
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        TIMER_ABSOLUTE_TO_START_BUTTON_DESC,
        TIMER_ABSOLUTE_TO_STOP_BUTTON_DESC,
    ),
    DeviceType.AIR_PURIFIER: (
        TIMER_ABSOLUTE_TO_START_BUTTON_DESC,
        TIMER_ABSOLUTE_TO_STOP_BUTTON_DESC,
    ),
    DeviceType.HUMIDIFIER: (
        TIMER_ABSOLUTE_TO_START_BUTTON_DESC,
        TIMER_ABSOLUTE_TO_STOP_BUTTON_DESC,
    ),
    DeviceType.ROBOT_CLEANER: (TIMER_ABSOLUTE_TO_START_BUTTON_DESC,),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for button platform."""
    entities: list[ButtonEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_BUTTON_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQButtonEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(description.key)
                )

    if entities:
        async_add_entities(entities)


class ThinQButtonEntity(ThinQEntity, ButtonEntity):
    """Represent a thinq button platform."""

    entity_description: ButtonEntityDescription

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.data.value is not None

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug(
            "[%s:%s] async_press",
            self.coordinator.device_name,
            self.property_id,
        )
        await self.async_call_api(self.coordinator.api.post(self.property_id, None))
