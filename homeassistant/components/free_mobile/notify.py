"""Support for Free Mobile SMS platform."""

from http import HTTPStatus
from typing import Any, override

from freesms import FreeClient
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .issue import async_deprecate_yaml_issue

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_ACCESS_TOKEN): cv.string}
)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> FreeSMSNotificationService | None:
    """Get the Free Mobile SMS notification service."""
    if config:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
        if result.get("type") is FlowResultType.CREATE_ENTRY or (
            result.get("type") is FlowResultType.ABORT
            and result.get("reason") == "already_configured"
        ):
            async_deprecate_yaml_issue(hass, config)
        else:
            async_deprecate_yaml_issue(hass, config, import_success=False)
        return None

    if discovery_info is None:
        return None

    entry = hass.config_entries.async_get_entry(discovery_info["entry_id"])
    if entry is None:
        return None

    return FreeSMSNotificationService(
        entry,
        discovery_info[CONF_USERNAME],
        discovery_info[CONF_ACCESS_TOKEN],
    )


class FreeSMSNotificationService(BaseNotificationService):
    """Implement a notification service for the Free Mobile SMS service."""

    def __init__(self, entry: ConfigEntry, username: str, access_token: str) -> None:
        """Initialize the service."""
        self._entry = entry
        self.free_client = FreeClient(username, access_token)

    @override
    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to the Free Mobile user cell."""
        resp: Any = self.free_client.send_sms(message)

        if resp.status_code == HTTPStatus.BAD_REQUEST:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="missing_parameter",
            )
        if resp.status_code == HTTPStatus.PAYMENT_REQUIRED:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="rate_limit_exceeded",
            )
        if resp.status_code == HTTPStatus.FORBIDDEN:
            self.hass.add_job(self._entry.async_start_reauth, self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            )
        if resp.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="server_error",
            )
