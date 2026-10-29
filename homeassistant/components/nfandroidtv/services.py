"""Actions for the Notifications for Android TV / Fire TV integration."""

from notifications_android_tv.notifications import Notifications
import probatio

from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.const import ATTR_ICON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import (
    ATTR_BGCOLOR,
    ATTR_DURATION,
    ATTR_FONTSIZE,
    ATTR_IMAGE,
    ATTR_INTERACTIVE,
    ATTR_POSITION,
    ATTR_TRANSPARENCY,
    DOMAIN,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Notification for Android TV / Fire TV integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema={
            probatio.Optional(ATTR_TITLE): cv.string,
            probatio.Required(ATTR_MESSAGE): cv.string,
            probatio.Optional(ATTR_IMAGE): MediaSelector({"accept": ["*"]}),
            probatio.Optional(ATTR_ICON): MediaSelector({"accept": ["*"]}),
            probatio.Optional(ATTR_POSITION): probatio.In(Notifications.POSITIONS),
            probatio.Optional(ATTR_DURATION): cv.positive_time_period,
            probatio.Optional(ATTR_INTERACTIVE): probatio.Boolean(),
            probatio.Optional(ATTR_BGCOLOR): probatio.In(Notifications.BKG_COLORS),
            probatio.Optional(ATTR_FONTSIZE): probatio.In(Notifications.FONTSIZES),
            probatio.Optional(ATTR_TRANSPARENCY): probatio.In(
                Notifications.TRANSPARENCIES
            ),
        },
        func="nfandroidtv_send_message",
    )
