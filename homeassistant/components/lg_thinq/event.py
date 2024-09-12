"""Support for event entity."""

from __future__ import annotations

import logging

from thinqconnect import DeviceType
from thinqconnect.integration import ActiveMode, ThinQPropertyEx

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity

NOTIFICATION_EVENT_DESC = EventEntityDescription(
    key=ThinQPropertyEx.NOTIFICATION,
    translation_key=ThinQPropertyEx.NOTIFICATION,
)
ERROR_EVENT_DESC = EventEntityDescription(
    key=ThinQPropertyEx.ERROR,
    translation_key=ThinQPropertyEx.ERROR,
)
WASHER_EVENTS: tuple[EventEntityDescription, ...] = (
    ERROR_EVENT_DESC,
    NOTIFICATION_EVENT_DESC,
)
DEVICE_TYPE_EVENT_MAP: dict[DeviceType, tuple[EventEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (NOTIFICATION_EVENT_DESC,),
    DeviceType.AIR_PURIFIER_FAN: (NOTIFICATION_EVENT_DESC,),
    DeviceType.AIR_PURIFIER: (NOTIFICATION_EVENT_DESC,),
    DeviceType.DEHUMIDIFIER: (NOTIFICATION_EVENT_DESC,),
    DeviceType.DISH_WASHER: (
        ERROR_EVENT_DESC,
        NOTIFICATION_EVENT_DESC,
    ),
    DeviceType.DRYER: WASHER_EVENTS,
    DeviceType.HUMIDIFIER: (NOTIFICATION_EVENT_DESC,),
    DeviceType.KIMCHI_REFRIGERATOR: (NOTIFICATION_EVENT_DESC,),
    DeviceType.MICROWAVE_OVEN: (NOTIFICATION_EVENT_DESC,),
    DeviceType.OVEN: (NOTIFICATION_EVENT_DESC,),
    DeviceType.REFRIGERATOR: (NOTIFICATION_EVENT_DESC,),
    DeviceType.ROBOT_CLEANER: (
        ERROR_EVENT_DESC,
        NOTIFICATION_EVENT_DESC,
    ),
    DeviceType.STICK_CLEANER: (NOTIFICATION_EVENT_DESC,),
    DeviceType.STYLER: WASHER_EVENTS,
    DeviceType.WASHCOMBO_MAIN: WASHER_EVENTS,
    DeviceType.WASHCOMBO_MINI: WASHER_EVENTS,
    DeviceType.WASHER: WASHER_EVENTS,
    DeviceType.WASHTOWER_DRYER: WASHER_EVENTS,
    DeviceType.WASHTOWER: WASHER_EVENTS,
    DeviceType.WASHTOWER_WASHER: WASHER_EVENTS,
    DeviceType.WINE_CELLAR: (NOTIFICATION_EVENT_DESC,),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for event platform."""
    entities: list[ThinQEventEntity] = []
    for coordinator in entry.runtime_data.values():
        if (
            descriptions := DEVICE_TYPE_EVENT_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQEventEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key, ActiveMode.READ_ONLY
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQEventEntity(ThinQEntity, EventEntity):
    """Represent an thinq event platform."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: EventEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize an event platform."""
        super().__init__(coordinator, entity_description, property_id)

        # For event types.
        self._attr_event_types = self.data.options

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        # Handle an event.
        if (value := self.data.value) is None or value not in self.event_types:
            return

        self._async_handle_update(value)
        if self.entity_description.key == ThinQPropertyEx.NOTIFICATION:
            self.coordinator.api.update_notification(None)

        _LOGGER.warning(
            "[%s:%s] update status:%s, event_types:%s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.event_types,
        )

    def _async_handle_update(self, value: str) -> None:
        """Handle the event."""
        self._trigger_event(value)
        self.async_write_ha_state()
