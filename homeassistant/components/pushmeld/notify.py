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
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
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

# The legacy notify loader stores services under this key.
NOTIFY_SERVICES_KEY = f"{NOTIFY_DOMAIN}_services"


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
    if not isinstance(entry_id, str):
        return None

    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.state not in (
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.LOADED,
    ):
        return None

    if not hasattr(entry, "runtime_data"):
        return None

    if not isinstance(maxcode, str) or not maxcode:
        error = ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="config_entry_error_invalid_maxcode",
        )
        _signal_setup_error(entry, error)
        raise error

    if not isinstance(name, str) or not (name := name.strip()):
        error = ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="config_entry_error_invalid_name",
        )
        _signal_setup_error(entry, error)
        raise error

    service_name = slugify(name)
    if hass.services.has_service(NOTIFY_DOMAIN, service_name):
        error = _name_exists_error(service_name)
        _signal_setup_error(entry, error)
        raise error

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
        if self.hass is None:
            return

        notify_services = self.hass.data.get(NOTIFY_SERVICES_KEY)
        if not notify_services or DOMAIN not in notify_services:
            return

        services = notify_services[DOMAIN]
        if self in services:
            services.remove(self)
            if not services:
                del notify_services[DOMAIN]

    def _signal_setup_error(self, error: BaseException) -> None:
        """Make config-entry setup report an error from the legacy loader."""
        if self._entry is None or not hasattr(self._entry, "runtime_data"):
            return

        _signal_setup_error(self._entry, error)

    def _signal_setup_ready(self) -> None:
        """Mark setup ready after the notify action is registered."""
        if self._entry is None or not hasattr(self._entry, "runtime_data"):
            return

        setup_future = self._entry.runtime_data.notify_service_ready
        if not setup_future.done():
            setup_future.set_result(None)

    def _service_is_owned(self) -> bool:
        """Return whether this service owns the registered notify action."""
        service = self.hass.services.async_services_for_domain(NOTIFY_DOMAIN).get(
            self._service_name
        )
        return (
            service is not None
            and getattr(service.job.target, "__self__", None) is self
        )

    @override
    async def async_setup(
        self,
        hass: HomeAssistant,
        service_name: str,
        target_service_name_prefix: str,
    ) -> None:
        """Prepare the service and propagate setup errors to the entry."""
        try:
            await super().async_setup(hass, service_name, target_service_name_prefix)
        except BaseException as err:
            self._signal_setup_error(err)
            raise

    @override
    async def async_register_services(self) -> None:
        """Register the notify action only while the config entry is active."""
        if not self._entry_is_active():
            # The legacy notify loader appends the service to its registry after
            # this method returns, so clean up on the next loop iteration.
            self.hass.loop.call_soon(self._remove_from_legacy_registry)
            self._signal_setup_error(
                ConfigEntryError(
                    translation_domain=DOMAIN,
                    translation_key="config_entry_error_not_active",
                )
            )
            return

        try:
            if self.hass.services.has_service(NOTIFY_DOMAIN, self._service_name):
                raise _name_exists_error(self._service_name)

            await super().async_register_services()
            if not self._service_is_owned():
                raise _name_exists_error(self._service_name)

            self._service_registered = True
            self._signal_setup_ready()
        except BaseException as err:
            self._signal_setup_error(err)
            raise

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


def _name_exists_error(service_name: str) -> ConfigEntryError:
    """Build the error for an occupied notification action name."""
    return ConfigEntryError(
        translation_domain=DOMAIN,
        translation_key="config_entry_error_name_exists",
        translation_placeholders={"service_name": service_name},
    )


def _signal_setup_error(entry: ConfigEntry[Any], error: BaseException) -> None:
    """Propagate a legacy notify setup error to the config entry."""
    if not hasattr(entry, "runtime_data"):
        return

    setup_future = entry.runtime_data.notify_service_ready
    if not setup_future.done():
        setup_future.set_exception(error)
