"""Support for LaMetric notifications."""

from typing import TYPE_CHECKING, Any, override

from demetriek import (
    AlarmSound,
    LaMetricError,
    Model,
    Notification,
    NotificationIconType,
    NotificationPriority,
    NotificationSound,
    Simple,
    Sound,
    SoundURL,
)
import probatio

from homeassistant.components.notify import (
    ATTR_DATA,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.const import CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.enum import try_parse_enum

from .const import (
    CONF_CYCLES,
    CONF_ICON_TYPE,
    CONF_PRIORITY,
    CONF_SOUND,
    CONF_SOUND_URL,
    DOMAIN,
)
from .coordinator import LaMetricConfigEntry, LaMetricDataUpdateCoordinator
from .entity import LaMetricEntity
from .helpers import has_audio, lametric_exception_handler

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
    return LaMetricNotificationService(entry.runtime_data)


class LaMetricNotificationService(BaseNotificationService):
    """Implement the notification service for LaMetric."""

    def __init__(self, coordinator: LaMetricDataUpdateCoordinator) -> None:
        """Initialize the service."""
        self.coordinator = coordinator

    @override
    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a LaMetric device."""
        if not (data := kwargs.get(ATTR_DATA)):
            data = {}

        builtin_sound: Sound | None = None
        if CONF_SOUND in data:
            snd: AlarmSound | NotificationSound | None
            if (snd := try_parse_enum(AlarmSound, data[CONF_SOUND])) is None and (
                snd := try_parse_enum(NotificationSound, data[CONF_SOUND])
            ) is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_sound",
                    translation_placeholders={"sound": str(data[CONF_SOUND])},
                )
            builtin_sound = Sound(sound=snd, category=None)

        # A built-in sound given as well plays when the URL cannot be fetched.
        sound: Sound | SoundURL | None = builtin_sound
        if CONF_SOUND_URL in data:
            try:
                url = cv.url(data[CONF_SOUND_URL])
            except probatio.Invalid as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_sound_url",
                    translation_placeholders={"url": str(data[CONF_SOUND_URL])},
                ) from err
            sound = SoundURL(url=url, fallback=builtin_sound)

        # Leave the sound out for a device that cannot play it, rather than have
        # it refuse the whole notification.
        if not has_audio(self.coordinator.data):
            sound = None

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
            await self.coordinator.lametric.notify(notification=notification)
        except LaMetricError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notification_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex
