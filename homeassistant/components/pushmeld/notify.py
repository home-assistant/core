# homeassistant/components/pushmeld/notify.py
"""PushMeld notification service."""

from collections.abc import Mapping
from typing import Any, override

from aiohttp import ClientError, ClientResponse, ClientSession, ClientTimeout
import probatio

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import API_URL, ATTR_DETAILS, CONF_MAXCODE, DOMAIN, REQUEST_TIMEOUT

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(probatio.Secret(CONF_MAXCODE)): cv.string,
    }
)


async def async_get_service(
    hass: HomeAssistant,
    _config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> PushMeldNotificationService | None:
    """Get the PushMeld notification service."""
    if not discovery_info:
        return None

    maxcode = discovery_info.get(CONF_MAXCODE)
    entry_id = discovery_info.get("entry_id")
    if not isinstance(maxcode, str) or not maxcode or not isinstance(entry_id, str):
        return None

    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None:
        return None

    service = PushMeldNotificationService(
        async_get_clientsession(hass),
        maxcode,
    )
    entry.runtime_data.notify_service = service
    return service


class PushMeldNotificationService(BaseNotificationService):
    """Implement the thin PushMeld HTTP adapter."""

    def __init__(self, session: ClientSession, maxcode: str) -> None:
        """Initialize the service with a MaxCode."""
        self._session = session
        self._maxcode = maxcode

    @override
    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a notification without interpreting the API response body."""
        data = kwargs.get(ATTR_DATA)
        payload: dict[str, Any] = {
            "title": kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
            "message": message,
        }

        if isinstance(data, Mapping) and ATTR_DETAILS in data:
            payload[ATTR_DETAILS] = data[ATTR_DETAILS]

        try:
            async with self._session.post(
                API_URL,
                headers={
                    "Authorization": f"MaxCode {self._maxcode}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            ) as response:
                if not 200 <= response.status < 300:
                    raise _request_failed(response)
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="timeout",
            ) from err
        except ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err


def _request_failed(response: ClientResponse) -> HomeAssistantError:
    """Build the error for a non-successful PushMeld response."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="request_failed",
        translation_placeholders={"status_code": str(response.status)},
    )
