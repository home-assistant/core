"""UniFi Protect Platform."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp.client_exceptions import ServerDisconnectedError
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import Bootstrap
from uiprotect.exceptions import BadRequest, ClientError, NotAuthorized

# Import the test_util.anonymize module from the uiprotect package
# in __init__ to ensure it gets imported in the executor since the
# diagnostics module will not be imported in the executor.
from uiprotect.test_util.anonymize import anonymize_data  # noqa: F401

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.typing import ConfigType

from .const import (
    AUTH_RETRIES,
    CONF_ALLOW_EA,
    DEVICES_THAT_ADOPT,
    DOMAIN,
    MIN_REQUIRED_PROTECT_V,
    PLATFORMS,
)
from .data import ProtectData, UFPConfigEntry
from .discovery import async_start_discovery
from .migrate import async_migrate_data
from .services import async_setup_services
from .utils import (
    _async_unifi_mac_from_hass,
    async_create_api_client,
    async_get_devices,
)
from .views import (
    SnapshotProxyView,
    ThumbnailProxyView,
    VideoEventProxyView,
    VideoProxyView,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=DEVICE_UPDATE_INTERVAL)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the UniFi Protect."""
    # Only start discovery once regardless of how many entries they have
    async_setup_services(hass)
    async_start_discovery(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: UFPConfigEntry) -> bool:
    """Set up the UniFi Protect config entries."""

    protect = async_create_api_client(hass, entry)
    _LOGGER.debug("Connect to UniFi Protect")

    try:
        await protect.update()
    except NotAuthorized as err:
        retry_key = f"{entry.entry_id}_auth"
        retries = hass.data.setdefault(DOMAIN, {}).get(retry_key, 0)
        if retries < AUTH_RETRIES:
            retries += 1
            hass.data[DOMAIN][retry_key] = retries
            raise ConfigEntryNotReady from err
        raise ConfigEntryAuthFailed(err) from err
    except (TimeoutError, ClientError, ServerDisconnectedError) as err:
        raise ConfigEntryNotReady from err

    data_service = ProtectData(hass, protect, SCAN_INTERVAL, entry)
    bootstrap = protect.bootstrap
    nvr_info = bootstrap.nvr
    auth_user = bootstrap.users.get(bootstrap.auth_user_id)

    # Check if API key is missing
    if not protect.is_api_key_set() and auth_user and nvr_info.can_write(auth_user):
        try:
            new_api_key = await protect.create_api_key(
                name=f"Home Assistant ({hass.config.location_name})"
            )
        except (NotAuthorized, BadRequest) as err:
            _LOGGER.error("Failed to create API key: %s", err)
        else:
            protect.set_api_key(new_api_key)
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_API_KEY: new_api_key}
            )

    if not protect.is_api_key_set():
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="api_key_required",
        )

    if auth_user and auth_user.cloud_account:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "cloud_user",
            is_fixable=True,
            is_persistent=False,
            learn_more_url="https://www.home-assistant.io/integrations/unifiprotect/#local-user",
            severity=IssueSeverity.ERROR,
            translation_key="cloud_user",
            data={"entry_id": entry.entry_id},
        )

    if nvr_info.version < MIN_REQUIRED_PROTECT_V:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="protect_version",
            translation_placeholders={
                "current_version": str(nvr_info.version),
                "min_version": str(MIN_REQUIRED_PROTECT_V),
            },
        )

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=nvr_info.mac)

    entry.runtime_data = data_service
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, data_service.async_stop)
    )

    await _async_setup_entry(hass, entry, data_service, bootstrap)

    return True


async def _async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    data_service: ProtectData,
    bootstrap: Bootstrap,
) -> None:
    await async_migrate_data(hass, entry, data_service.api, bootstrap)
    data_service.async_setup()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.http.register_view(ThumbnailProxyView(hass))
    hass.http.register_view(SnapshotProxyView(hass))
    hass.http.register_view(VideoProxyView(hass))
    hass.http.register_view(VideoEventProxyView(hass))


async def async_unload_entry(hass: HomeAssistant, entry: UFPConfigEntry) -> bool:
    """Unload UniFi Protect config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_stop()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: UFPConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove ufp config entry from a device."""
    unifi_macs = {
        _async_unifi_mac_from_hass(connection[1])
        for connection in device_entry.connections
        if connection[0] == dr.CONNECTION_NETWORK_MAC
    }
    api = config_entry.runtime_data.api
    if api.bootstrap.nvr.mac in unifi_macs:
        return False
    for device in async_get_devices(api.bootstrap, DEVICES_THAT_ADOPT):
        if device.is_adopted_by_us and device.mac in unifi_macs:
            return False
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entry."""
    _LOGGER.debug("Migrating configuration from version %s", entry.version)

    if entry.version > 1:
        return False

    if entry.version == 1:
        options = dict(entry.options)
        if CONF_ALLOW_EA in options:
            options.pop(CONF_ALLOW_EA)
        hass.config_entries.async_update_entry(
            entry, unique_id=str(entry.unique_id), version=2, options=options
        )

    _LOGGER.debug("Migration to configuration version %s successful", entry.version)

    return True
