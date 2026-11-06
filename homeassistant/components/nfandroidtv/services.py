"""Actions for the Notifications for Android TV / Fire TV integration."""

from notifications_android_tv.notifications import Notifications
import probatio

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.selector import MediaSelector

from .const import DOMAIN, NFAndroidTVService, NFAndroidTVServiceArgument


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Notification for Android TV / Fire TV integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        NFAndroidTVService.SEND_MESSAGE,
        entity_domain=NOTIFY_DOMAIN,
        schema={
            probatio.Optional(NFAndroidTVServiceArgument.TITLE): cv.string,
            probatio.Required(NFAndroidTVServiceArgument.MESSAGE): cv.string,
            probatio.Optional(NFAndroidTVServiceArgument.IMAGE): MediaSelector(
                {"accept": ["*"]}
            ),
            probatio.Optional(NFAndroidTVServiceArgument.ICON): MediaSelector(
                {"accept": ["*"]}
            ),
            probatio.Optional(NFAndroidTVServiceArgument.POSITION): probatio.In(
                Notifications.POSITIONS
            ),
            probatio.Optional(
                NFAndroidTVServiceArgument.DURATION
            ): cv.positive_time_period,
            probatio.Optional(
                NFAndroidTVServiceArgument.INTERACTIVE
            ): probatio.Boolean(),
            probatio.Optional(NFAndroidTVServiceArgument.BACKGROUND_COLOR): probatio.In(
                Notifications.BKG_COLORS
            ),
            probatio.Optional(NFAndroidTVServiceArgument.FONTSIZE): probatio.In(
                Notifications.FONTSIZES
            ),
            probatio.Optional(NFAndroidTVServiceArgument.TRANSPARENCY): probatio.In(
                Notifications.TRANSPARENCIES
            ),
        },
        func="nfandroidtv_send_message",
    )
