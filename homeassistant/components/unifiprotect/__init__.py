"""UniFi Protect Platform."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp.client_exceptions import ServerDisconnectedError
from uiprotect.api import DEVICE_UPDATE_INTERVAL
from uiprotect.data import Bootstrap
from uiprotect.data.types import FirmwareReleaseChannel
from uiprotect.exceptions import ClientError, NotAuthorized

# Import the test_util.anonymize module from the uiprotect package
# in __init__ to ensure it gets imported in the executor since the
# diagnostics module will not be imported in the executor.
from uiprotect.test_util.anonymize import anonymize_data  # noqa: F401

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
    OUTDATED_LOG_MESSAGE,
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
from .views import ThumbnailProxyView, VideoProxyView

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=DEVICE_UPDATE_INTERVAL)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

EARLY_ACCESS_URL = (
    "https://www.home-assistant.io/integrations/unifiprotect#software-support"
)


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
        _LOGGER.error(
            OUTDATED_LOG_MESSAGE,
            nvr_info.version,
            MIN_REQUIRED_PROTECT_V,
        )
        return False

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=nvr_info.mac)

    entry.runtime_data = data_service
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, data_service.async_stop)
    )

    if not entry.options.get(CONF_ALLOW_EA, False) and (
        await nvr_info.get_is_prerelease()
        or nvr_info.release_channel != FirmwareReleaseChannel.RELEASE
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "ea_channel_warning",
            is_fixable=True,
            is_persistent=False,
            learn_more_url=EARLY_ACCESS_URL,
            severity=IssueSeverity.WARNING,
            translation_key="ea_channel_warning",
            translation_placeholders={"version": str(nvr_info.version)},
            data={"entry_id": entry.entry_id},
        )

    try:
        await _async_setup_entry(hass, entry, data_service, bootstrap)
    except Exception as err:
        if await nvr_info.get_is_prerelease():
            # If they are running a pre-release, its quite common for setup
            # to fail so we want to create a repair issue for them so its
            # obvious what the problem is.
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"ea_setup_failed_{nvr_info.version}",
                is_fixable=False,
                is_persistent=False,
                learn_more_url="https://www.home-assistant.io/integrations/unifiprotect#about-unifi-early-access",
                severity=IssueSeverity.ERROR,
                translation_key="ea_setup_failed",
                translation_placeholders={
                    "error": str(err),
                    "version": str(nvr_info.version),
                },
            )
            ir.async_delete_issue(hass, DOMAIN, "ea_channel_warning")
            _LOGGER.exception("Error setting up UniFi Protect integration")
        raise

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
    hass.http.register_view(VideoProxyView(hass))


async def _async_options_updated(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


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
