"""The flume integration."""

from __future__ import annotations

from pyflume import FlumeAuth, FlumeDeviceList
from requests import Session
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.selector import ConfigEntrySelector

from .const import (
    BASE_TOKEN_FILENAME,
    DOMAIN,
    FLUME_AUTH,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_NOTIFICATIONS_COORDINATOR,
    PLATFORMS,
)
from .coordinator import FlumeNotificationDataUpdateCoordinator

SERVICE_LIST_NOTIFICATIONS = "list_notifications"
CONF_CONFIG_ENTRY = "config_entry"
LIST_NOTIFICATIONS_SERVICE_SCHEMA = vol.All(
    {
        vol.Required(CONF_CONFIG_ENTRY): ConfigEntrySelector(),
    },
)


def _setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[FlumeAuth, FlumeDeviceList, Session]:
    """Config entry set up in executor."""
    config = entry.data

    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    flume_token_full_path = hass.config.path(f"{BASE_TOKEN_FILENAME}-{username}")

    http_session = Session()

    try:
        flume_auth = FlumeAuth(
            username,
            password,
            client_id,
            client_secret,
            flume_token_file=flume_token_full_path,
            http_session=http_session,
        )
        flume_devices = FlumeDeviceList(flume_auth, http_session=http_session)
    except RequestException as ex:
        raise ConfigEntryNotReady from ex
    except Exception as ex:
        raise ConfigEntryAuthFailed from ex

    return flume_auth, flume_devices, http_session


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up flume from a config entry."""

    flume_auth, flume_devices, http_session = await hass.async_add_executor_job(
        _setup_entry, hass, entry
    )
    notification_coordinator = FlumeNotificationDataUpdateCoordinator(
        hass=hass, auth=flume_auth
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        FLUME_DEVICES: flume_devices,
        FLUME_AUTH: flume_auth,
        FLUME_HTTP_SESSION: http_session,
        FLUME_NOTIFICATIONS_COORDINATOR: notification_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    setup_service(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    hass.data[DOMAIN][entry.entry_id][FLUME_HTTP_SESSION].close()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


def setup_service(hass: HomeAssistant) -> None:
    """Add the services for the flume integration."""

    @callback
    def list_notifications(call: ServiceCall) -> ServiceResponse:
        """Return the user notifications."""
        entry_id: str = call.data[CONF_CONFIG_ENTRY]
        entry: ConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            raise ValueError(f"Invalid config entry: {entry_id}")
        if not (flume_domain_data := hass.data[DOMAIN].get(entry_id)):
            raise ValueError(f"Config entry not loaded: {entry_id}")
        return {
            "notifications": flume_domain_data[
                FLUME_NOTIFICATIONS_COORDINATOR
            ].notifications
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_NOTIFICATIONS,
        list_notifications,
        schema=LIST_NOTIFICATIONS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
