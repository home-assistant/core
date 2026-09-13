"""Support for LaMetric notifications."""

from typing import TYPE_CHECKING, Any, override

from demetriek import (
    AlarmSound,
    LaMetricDevice,
    LaMetricError,
    Model,
    Notification,
    NotificationIconType,
    NotificationPriority,
    NotificationSound,
    Simple,
    Sound,
)

from homeassistant.components.notify import (
    ATTR_DATA,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.const import CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.enum import try_parse_enum

from .const import CONF_CYCLES, CONF_ICON_TYPE, CONF_PRIORITY, CONF_SOUND
from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity
from .helpers import lametric_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMetricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LaMetric notify entity based on a config entry."""
    async_add_entities([LaMetricNotifyEntity(entry.runtime_data)])


class LaMetricNotifyEntity(LaMetricEntity, NotifyEntity):
    """Representation of a LaMetric notify entity."""

    _attr_translation_key = "message"

    def __init__(self, coordinator: LaMetricDataUpdateCoordinator) -> None:
        """Initialize the notify entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.serial_number}-message"

    @lametric_exception_handler
    @override
    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to the LaMetric device."""
        await self.coordinator.lametric.notify(
            notification=Notification(
                icon_type=NotificationIconType.NONE,
                priority=NotificationPriority.INFO,
                model=Model(frames=[Simple(text=message)]),
            )
        )


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> LaMetricNotificationService | None:
    """Get the LaMetric notification service."""
    if discovery_info is None:
        return None
    entry: LaMetricConfigEntry | None = hass.config_entries.async_get_entry(
        discovery_info["entry_id"]
    )
    if TYPE_CHECKING:
        assert entry is not None
    return LaMetricNotificationService(entry.runtime_data.lametric)


class LaMetricNotificationService(BaseNotificationService):
    """Implement the notification service for LaMetric."""

    def __init__(self, lametric: LaMetricDevice) -> None:
        """Initialize the service."""
        self.lametric = lametric

    @override
    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a LaMetric device."""
        if not (data := kwargs.get(ATTR_DATA)):
            data = {}

        sound = None
        if CONF_SOUND in data:
            snd: AlarmSound | NotificationSound | None
            if (snd := try_parse_enum(AlarmSound, data[CONF_SOUND])) is None and (
                snd := try_parse_enum(NotificationSound, data[CONF_SOUND])
            ) is None:
                raise ServiceValidationError("Unknown sound provided")
            sound = Sound(sound=snd, category=None)

        notification = Notification(
            icon_type=NotificationIconType(data.get(CONF_ICON_TYPE, "none")),
            priority=NotificationPriority(data.get(CONF_PRIORITY, "info")),
            model=Model(
                frames=[
                    Simple(
                        icon=data.get(CONF_ICON, "a7956"),
                        text=message,
                    )
                ],
                cycles=int(data.get(CONF_CYCLES, 1)),
                sound=sound,
            ),
        )

        try:
            await self.lametric.notify(notification=notification)
        except LaMetricError as ex:
            raise HomeAssistantError("Could not send LaMetric notification") from ex
