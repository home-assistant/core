"""Support for Sinch notifications."""

import logging
from typing import Any, override

from clx.xms.api import MtBatchTextSmsResult
from clx.xms.client import Client
from clx.xms.exceptions import (
    ErrorResponseException,
    NotFoundException,
    UnauthorizedException,
    UnexpectedResponseException,
)
import probatio

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY, CONF_SENDER
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DOMAIN = "sinch"

CONF_SERVICE_PLAN_ID = "service_plan_id"
CONF_DEFAULT_RECIPIENTS = "default_recipients"

ATTR_SENDER = CONF_SENDER

DEFAULT_SENDER = "Home Assistant"

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
        probatio.Required(CONF_SERVICE_PLAN_ID): cv.string,
        probatio.Optional(CONF_SENDER, default=DEFAULT_SENDER): cv.string,
        probatio.Optional(CONF_DEFAULT_RECIPIENTS, default=[]): probatio.All(
            probatio.EnsureList(), [cv.string]
        ),
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SinchNotificationService:
    """Get the Sinch notification service."""
    return SinchNotificationService(config)


class SinchNotificationService(BaseNotificationService):
    """Send Notifications to Sinch SMS recipients."""

    def __init__(self, config):
        """Initialize the service."""
        self.default_recipients = config[CONF_DEFAULT_RECIPIENTS]
        self.sender = config[CONF_SENDER]
        self.client = Client(config[CONF_SERVICE_PLAN_ID], config[CONF_API_KEY])

    @override
    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        targets = kwargs.get(ATTR_TARGET, self.default_recipients)
        data = kwargs.get(ATTR_DATA) or {}

        clx_args = {ATTR_MESSAGE: message, ATTR_SENDER: self.sender}

        if ATTR_SENDER in data:
            clx_args[ATTR_SENDER] = data[ATTR_SENDER]

        if not targets:
            _LOGGER.error("At least 1 target is required")
            return

        try:
            for target in targets:
                result: MtBatchTextSmsResult = self.client.create_text_message(
                    clx_args[ATTR_SENDER], target, clx_args[ATTR_MESSAGE]
                )
                batch_id = result.batch_id
                _LOGGER.debug(
                    'Successfully sent SMS to "%s" (batch_id: %s)', target, batch_id
                )
        except UnauthorizedException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unauthorized",
            ) from ex
        except (
            ErrorResponseException,
            NotFoundException,
            UnexpectedResponseException,
        ) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
            ) from ex
