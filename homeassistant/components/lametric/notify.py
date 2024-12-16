"""Support for LaMetric notifications."""

from __future__ import annotations

from typing import Any

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

from homeassistant.components.notify import ATTR_DATA, BaseNotificationService
from homeassistant.const import CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.enum import try_parse_enum

from .const import CONF_CYCLES, CONF_ICON_TYPE, CONF_PRIORITY, CONF_SOUND, DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> LaMetricNotificationService | None:
    """Get the LaMetric notification service."""
    if discovery_info is None:
        return None
    coordinator: LaMetricDataUpdateCoordinator = hass.data[DOMAIN][
        discovery_info["entry_id"]
    ]
    return LaMetricNotificationService(coordinator.lametric)


class LaMetricNotificationService(BaseNotificationService):
    """Implement the notification service for LaMetric."""

    def __init__(self, lametric: LaMetricDevice) -> None:
        """Initialize the service."""
        self.lametric = lametric

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
