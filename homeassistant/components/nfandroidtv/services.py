"""Actions for the Notifications for Android TV / Fire TV integration."""

from notifications_android_tv.notifications import Notifications
import voluptuous as vol

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
            vol.Optional(ATTR_TITLE): cv.string,
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_IMAGE): MediaSelector({"accept": ["image/*", "video/*"]}),
            vol.Optional(ATTR_ICON): MediaSelector({"accept": ["image/*", "video/*"]}),
            vol.Optional(ATTR_POSITION): vol.In(Notifications.POSITIONS),
            vol.Optional(ATTR_DURATION): vol.All(cv.time_period),
            vol.Optional(ATTR_INTERACTIVE): cv.boolean,
            vol.Optional(ATTR_BGCOLOR): vol.In(Notifications.BKG_COLORS),
            vol.Optional(ATTR_FONTSIZE): vol.In(Notifications.FONTSIZES),
            vol.Optional(ATTR_TRANSPARENCY): vol.In(Notifications.TRANSPARENCIES),
        },
        func="nfandroidtv_send_message",
    )
