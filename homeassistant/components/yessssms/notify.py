"""Support for the YesssSMS platform."""
import logging

from YesssSMS import YesssSMS
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_PASSWORD, CONF_RECIPIENT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv

from .const import CONF_PROVIDER

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_RECIPIENT): cv.string,
        vol.Optional(CONF_PROVIDER, default="YESSS"): cv.string,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the YesssSMS notification service."""

    try:
        yesss = YesssSMS(
            config[CONF_USERNAME], config[CONF_PASSWORD], provider=config[CONF_PROVIDER]
        )
    except YesssSMS.UnsupportedProviderError as ex:
        _LOGGER.error("Unknown provider: %s", ex)
        return None
    try:
        if not yesss.login_data_valid():
            _LOGGER.error(
                "Login data is not valid! Please double check your login data at %s",
                yesss.get_login_url(),
            )
            return None

        _LOGGER.debug("Login data for '%s' valid", yesss.get_provider())
    except YesssSMS.ConnectionError:
        _LOGGER.warning(
            "Connection Error, could not verify login data for '%s'",
            yesss.get_provider(),
        )

    _LOGGER.debug(
        "initialized; library version: %s, with %s",
        yesss.version(),
        yesss.get_provider(),
    )
    return YesssSMSNotificationService(yesss, config[CONF_RECIPIENT])


class YesssSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the YesssSMS service."""

    def __init__(self, client, recipient):
        """Initialize the service."""
        self.yesss = client
        self._recipient = recipient

    def send_message(self, message="", **kwargs):
        """Send a SMS message via Yesss.at's website."""
        if self.yesss.account_is_suspended():
            # only retry to login after Home Assistant was restarted with (hopefully)
            # new login data.
            _LOGGER.error(
                "Account is suspended, cannot send SMS. "
                "Check your login data and restart Home Assistant"
            )
            return
        try:
            self.yesss.send(self._recipient, message)
        except self.yesss.NoRecipientError as ex:
            _LOGGER.error(
                "You need to provide a recipient for SMS notification: %s", ex
            )
        except self.yesss.EmptyMessageError as ex:
            _LOGGER.error("Cannot send empty SMS message: %s", ex)
        except self.yesss.SMSSendingError as ex:
            _LOGGER.error(ex)
        except self.yesss.ConnectionError as ex:
            _LOGGER.error(
                "Unable to connect to server of provider (%s): %s",
                self.yesss.get_provider(),
                ex,
            )
        except self.yesss.AccountSuspendedError as ex:
            _LOGGER.error(
                "Wrong login credentials!! Verify correct credentials and "
                "restart Home Assistant: %s",
                ex,
            )
        except self.yesss.LoginError as ex:
            _LOGGER.error("Wrong login credentials: %s", ex)
        else:
            _LOGGER.info("SMS sent")
