"""Pushover platform for notify component."""

from typing import TYPE_CHECKING, Any, override

from pushover_complete import BadAPIRequestError, PushoverAPI

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ATTACHMENT,
    ATTR_CALLBACK_URL,
    ATTR_EXPIRE,
    ATTR_HTML,
    ATTR_PRIORITY,
    ATTR_RETRY,
    ATTR_SOUND,
    ATTR_TIMESTAMP,
    ATTR_TTL,
    ATTR_URL,
    ATTR_URL_TITLE,
    CONF_USER_KEY,
    DOMAIN,
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> PushoverNotificationService | None:
    """Get the Pushover notification service."""
    if TYPE_CHECKING:
        assert discovery_info is not None
    entry = hass.config_entries.async_get_entry(discovery_info["entry_id"])
    if TYPE_CHECKING:
        assert entry is not None
    return PushoverNotificationService(
        hass, entry.runtime_data, discovery_info[CONF_USER_KEY]
    )


class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(
        self, hass: HomeAssistant, pushover: PushoverAPI, user_key: str
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._user_key = user_key
        self.pushover = pushover

    @override
    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        # Extract params from data dict
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA) or {}
        url = data.get(ATTR_URL)
        url_title = data.get(ATTR_URL_TITLE)
        priority = data.get(ATTR_PRIORITY)
        retry = data.get(ATTR_RETRY)
        expire = data.get(ATTR_EXPIRE)
        ttl = data.get(ATTR_TTL)
        callback_url = data.get(ATTR_CALLBACK_URL)
        timestamp = data.get(ATTR_TIMESTAMP)
        sound = data.get(ATTR_SOUND)
        html = 1 if data.get(ATTR_HTML, False) else 0

        # Check for attachment
        if (image := data.get(ATTR_ATTACHMENT)) is not None:
            # Only allow attachments from whitelisted paths, check valid path
            if not self._hass.config.is_allowed_path(data[ATTR_ATTACHMENT]):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="attachment_not_allowed",
                    translation_placeholders={"attachment": data[ATTR_ATTACHMENT]},
                )
            try:
                # pylint: disable-next=consider-using-with
                file_handle = open(data[ATTR_ATTACHMENT], "rb")
            except OSError as err:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="attachment_open_failed",
                    translation_placeholders={"attachment": data[ATTR_ATTACHMENT]},
                ) from err
            # Replace the attachment identifier with file object.
            image = file_handle

        try:
            self.pushover.send_message(
                user=self._user_key,
                message=message,
                device=",".join(kwargs.get(ATTR_TARGET, [])),
                title=title,
                url=url,
                url_title=url_title,
                image=image,
                priority=priority,
                retry=retry,
                expire=expire,
                callback_url=callback_url,
                timestamp=timestamp,
                sound=sound,
                html=html,
                ttl=ttl,
            )
        except BadAPIRequestError as err:
            raise HomeAssistantError(str(err)) from err
