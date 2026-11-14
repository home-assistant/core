"""Support for LaMetric time services."""

from enum import StrEnum

from demetriek import (
    AlarmSound,
    Chart,
    Goal,
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

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util.enum import try_parse_enum

from .const import DOMAIN
from .coordinator import LaMetricDataUpdateCoordinator
from .helpers import (
    async_get_coordinator_by_device_id,
    async_resolve_sound_url,
    has_audio,
    media_content_id,
)


class LaMetricService(StrEnum):
    """Store keys for LaMetric services."""

    CHART = "chart"
    MESSAGE = "message"


class LaMetricServiceArgument(StrEnum):
    """Store keys for LaMetric service arguments."""

    DATA = "data"
    SOUND = "sound"
    SOUND_URL = "sound_url"
    CYCLES = "cycles"
    REPEAT = "repeat"
    ICON_TYPE = "icon_type"
    PRIORITY = "priority"
    MESSAGE = "message"
    ICON = "icon"


SERVICE_BASE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): cv.string,
        probatio.Optional(LaMetricServiceArgument.CYCLES, default=1): cv.positive_int,
        probatio.Optional(
            LaMetricServiceArgument.ICON_TYPE, default=NotificationIconType.NONE
        ): probatio.Coerce(NotificationIconType),
        probatio.Optional(
            LaMetricServiceArgument.PRIORITY, default=NotificationPriority.INFO
        ): probatio.Coerce(NotificationPriority),
        probatio.Optional(LaMetricServiceArgument.SOUND): probatio.Any(
            probatio.Coerce(AlarmSound), probatio.Coerce(NotificationSound)
        ),
        probatio.Optional(LaMetricServiceArgument.REPEAT, default=1): probatio.All(
            probatio.Coerce(int), probatio.NonNegative()
        ),
        probatio.Optional(LaMetricServiceArgument.SOUND_URL): media_content_id,
    }
)

SERVICE_MESSAGE_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Required(LaMetricServiceArgument.MESSAGE): cv.string,
        probatio.Optional(LaMetricServiceArgument.ICON): cv.string,
    }
)

SERVICE_CHART_SCHEMA = SERVICE_BASE_SCHEMA.extend(
    {
        probatio.Required(LaMetricServiceArgument.DATA): probatio.All(
            probatio.EnsureList(), [probatio.Coerce(int)]
        ),
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the LaMetric integration."""

    async def _async_service_chart(call: ServiceCall) -> None:
        """Send a chart to a LaMetric device."""
        coordinator = async_get_coordinator_by_device_id(
            hass, call.data[CommonServiceArgument.DEVICE_ID]
        )
        await async_send_notification(
            coordinator, call, [Chart(data=call.data[LaMetricServiceArgument.DATA])]
        )

    async def _async_service_message(call: ServiceCall) -> None:
        """Send a message to a LaMetric device."""
        coordinator = async_get_coordinator_by_device_id(
            hass, call.data[CommonServiceArgument.DEVICE_ID]
        )
        await async_send_notification(
            coordinator,
            call,
            [
                Simple(
                    icon=call.data.get(LaMetricServiceArgument.ICON, "a7956"),
                    text=call.data[LaMetricServiceArgument.MESSAGE],
                )
            ],
        )

    hass.services.async_register(
        DOMAIN,
        LaMetricService.CHART,
        _async_service_chart,
        schema=SERVICE_CHART_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        LaMetricService.MESSAGE,
        _async_service_message,
        schema=SERVICE_MESSAGE_SCHEMA,
        description_placeholders={"icons_url": "https://developer.lametric.com/icons"},
    )


async def async_send_notification(
    coordinator: LaMetricDataUpdateCoordinator,
    call: ServiceCall,
    frames: list[Chart | Goal | Simple],
) -> None:
    """Send a notification to an LaMetric device."""
    builtin_sound: Sound | None = None
    if LaMetricServiceArgument.SOUND in call.data:
        snd: AlarmSound | NotificationSound | None
        if (
            snd := try_parse_enum(AlarmSound, call.data[LaMetricServiceArgument.SOUND])
        ) is None and (
            snd := try_parse_enum(
                NotificationSound, call.data[LaMetricServiceArgument.SOUND]
            )
        ) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_sound",
                translation_placeholders={
                    "sound": str(call.data[LaMetricServiceArgument.SOUND])
                },
            )
        builtin_sound = Sound(
            sound=snd,
            category=None,
            repeat=call.data[LaMetricServiceArgument.REPEAT],
        )

    # A built-in sound given as well plays when the URL cannot be fetched.
    sound: Sound | SoundURL | None = builtin_sound
    if LaMetricServiceArgument.SOUND_URL in call.data:
        sound = SoundURL(
            url=await async_resolve_sound_url(
                coordinator.hass, call.data[LaMetricServiceArgument.SOUND_URL]
            ),
            fallback=builtin_sound,
        )

    # Leave the sound out for a device that cannot play it, rather than have
    # it refuse the whole notification.
    if not has_audio(coordinator.data):
        sound = None

    notification = Notification(
        icon_type=NotificationIconType(call.data[LaMetricServiceArgument.ICON_TYPE]),
        priority=NotificationPriority(call.data[LaMetricServiceArgument.PRIORITY]),
        model=Model(
            frames=frames,
            cycles=call.data[LaMetricServiceArgument.CYCLES],
            sound=sound,
        ),
    )

    try:
        await coordinator.lametric.notify(notification=notification)
    except LaMetricError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="notification_failed",
            translation_placeholders={"error": str(ex)},
        ) from ex
