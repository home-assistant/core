"""Support for text entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from thinqconnect import DeviceType
from thinqconnect.integration import ActiveMode, TimerProperty

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity


@dataclass(frozen=True, kw_only=True)
class ThinQTextEntityDescription(TextEntityDescription):
    """Describes ThinQ text entity."""

    default_hint: str | None = None


TIMER_ABSOLUTE_TO_START_TEXT_DESC = ThinQTextEntityDescription(
    key=TimerProperty.ABSOLUTE_TO_START,
    translation_key=TimerProperty.ABSOLUTE_TO_START,
    default_hint="Input format 24-hour clock",
)
TIMER_ABSOLUTE_TO_STOP_TEXT_DESC = ThinQTextEntityDescription(
    key=TimerProperty.ABSOLUTE_TO_STOP,
    translation_key=TimerProperty.ABSOLUTE_TO_STOP,
    default_hint="Input format 24-hour clock",
)

DEVICE_TYPE_TEXT_MAP: dict[DeviceType, tuple[ThinQTextEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        TIMER_ABSOLUTE_TO_START_TEXT_DESC,
        TIMER_ABSOLUTE_TO_STOP_TEXT_DESC,
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        TIMER_ABSOLUTE_TO_START_TEXT_DESC,
        TIMER_ABSOLUTE_TO_STOP_TEXT_DESC,
    ),
    DeviceType.AIR_PURIFIER: (
        TIMER_ABSOLUTE_TO_START_TEXT_DESC,
        TIMER_ABSOLUTE_TO_STOP_TEXT_DESC,
    ),
    DeviceType.HUMIDIFIER: (
        TIMER_ABSOLUTE_TO_START_TEXT_DESC,
        TIMER_ABSOLUTE_TO_STOP_TEXT_DESC,
    ),
    DeviceType.ROBOT_CLEANER: (TIMER_ABSOLUTE_TO_START_TEXT_DESC,),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for text platform."""
    entities: list[ThinQTextEntity] = []
    for coordinator in entry.runtime_data.values():
        if (
            descriptions := DEVICE_TYPE_TEXT_MAP.get(coordinator.api.device.device_type)
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQTextEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key, ActiveMode.READ_WRITE
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQTextEntity(ThinQEntity, TextEntity):
    """Represent a thinq text platform."""

    entity_description: ThinQTextEntityDescription

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()
        if (value := self.data.value) is not None:
            self._attr_native_value = value
        else:
            self._attr_native_value = self.entity_description.default_hint

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.native_value,
        )

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        _LOGGER.debug(
            "[%s:%s] async_set_value: %s",
            self.coordinator.device_name,
            self.property_id,
            value,
        )
        await self.async_call_api(self.coordinator.api.post(self.property_id, value))
