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
    DOMAIN as NOTIFY_DOMAIN,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.components.notify.legacy import NOTIFY_SERVICES
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify

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
    name = discovery_info.get(CONF_NAME)
    entry_id = discovery_info.get("entry_id")
    if (
        not isinstance(maxcode, str)
        or not maxcode
        or not isinstance(name, str)
        or not name.strip()
        or not isinstance(entry_id, str)
    ):
        return None

    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.state not in (
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.LOADED,
    ):
        return None

    if not hasattr(entry, "runtime_data"):
        return None

    service_name = slugify(name)
    if hass.services.has_service(NOTIFY_DOMAIN, service_name):
        return None

    service = PushMeldNotificationService(
        async_get_clientsession(hass),
        maxcode,
        entry,
    )
    entry.runtime_data.notify_service = service
    entry.async_on_unload(service.async_unregister_services)
    return service


class PushMeldNotificationService(BaseNotificationService):
    """Implement the thin PushMeld HTTP adapter."""

    def __init__(
        self,
        session: ClientSession,
        maxcode: str,
        entry: ConfigEntry[Any] | None = None,
    ) -> None:
        """Initialize the service with a MaxCode."""
        self._session = session
        self._maxcode = maxcode
        self._entry = entry
        self._service_registered = False

    def _entry_is_active(self) -> bool:
        """Return whether the config entry may still register its service."""
        if self._entry is None:
            return True

        if self._entry.state not in (
            ConfigEntryState.SETUP_IN_PROGRESS,
            ConfigEntryState.LOADED,
        ):
            return False

        return self._entry_owns_runtime_service()

    def _entry_owns_runtime_service(self) -> bool:
        """Return whether this service is the entry's current service."""
        if self._entry is None:
            return True

        if not hasattr(self._entry, "runtime_data"):
            return False

        return self._entry.runtime_data.notify_service is self

    def _remove_from_legacy_registry(self) -> None:
        """Remove this service instance from the legacy notify registry."""
        notify_services = self.hass.data.get(NOTIFY_SERVICES)
        if not notify_services or DOMAIN not in notify_services:
            return

        services = notify_services[DOMAIN]
        if self in services:
            services.remove(self)
            if not services:
                del notify_services[DOMAIN]

    @override
    async def async_register_services(self) -> None:
        """Register the notify action only while the config entry is active."""
        if not self._entry_is_active():
            # The legacy notify loader appends the service to its registry after
            # this method returns, so clean up on the next loop iteration.
            self.hass.loop.call_soon(self._remove_from_legacy_registry)
            return

        if self.hass.services.has_service(NOTIFY_DOMAIN, self._service_name):
            return

        await super().async_register_services()
        self._service_registered = self.hass.services.has_service(
            NOTIFY_DOMAIN, self._service_name
        )

    @override
    async def async_unregister_services(self) -> None:
        """Unregister only the notify action owned by this service."""
        if self._service_registered:
            if self._entry_owns_runtime_service():
                await super().async_unregister_services()
            self._service_registered = False

        self._remove_from_legacy_registry()

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
