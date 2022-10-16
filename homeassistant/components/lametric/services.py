"""Support for LaMetric time services."""
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
)
import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_ICON
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CYCLES,
    CONF_ICON_TYPE,
    CONF_MESSAGE,
    CONF_PRIORITY,
    CONF_SOUND,
    DOMAIN,
    SERVICE_MESSAGE,
)
from .coordinator import LaMetricDataUpdateCoordinator
from .helpers import async_get_coordinator_by_device_id

SERVICE_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_MESSAGE): cv.string,
        vol.Optional(CONF_CYCLES, default=1): cv.positive_int,
        vol.Optional(CONF_ICON_TYPE, default=NotificationIconType.NONE): vol.Coerce(
            NotificationIconType
        ),
        vol.Optional(CONF_PRIORITY, default=NotificationPriority.INFO): vol.Coerce(
            NotificationPriority
        ),
        vol.Optional(CONF_SOUND): vol.Any(
            vol.Coerce(AlarmSound), vol.Coerce(NotificationSound)
        ),
        vol.Optional(CONF_ICON): cv.string,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the LaMetric integration."""

    async def _async_service_text(call: ServiceCall) -> None:
        """Send a message to a LaMetric device."""
        coordinator = async_get_coordinator_by_device_id(
            hass, call.data[CONF_DEVICE_ID]
        )
        await async_service_text(coordinator, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_MESSAGE,
        _async_service_text,
        schema=SERVICE_MESSAGE_SCHEMA,
    )


async def async_service_text(
    coordinator: LaMetricDataUpdateCoordinator, call: ServiceCall
) -> None:
    """Send a message to an LaMetric device."""
    sound = None
    if CONF_SOUND in call.data:
        sound = Sound(id=call.data[CONF_SOUND], category=None)

    notification = Notification(
        icon_type=NotificationIconType(call.data[CONF_ICON_TYPE]),
        priority=NotificationPriority(call.data.get(CONF_PRIORITY)),
        model=Model(
            frames=[
                Simple(
                    icon=call.data.get(CONF_ICON),
                    text=call.data[CONF_MESSAGE],
                )
            ],
            cycles=call.data[CONF_CYCLES],
            sound=sound,
        ),
    )

    try:
        await coordinator.lametric.notify(notification=notification)
    except LaMetricError as ex:
        raise HomeAssistantError("Could not send LaMetric notification") from ex
