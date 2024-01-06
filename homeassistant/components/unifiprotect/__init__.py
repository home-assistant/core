"""UniFi Protect Platform."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiohttp.client_exceptions import ServerDisconnectedError
from pyunifiprotect.exceptions import ClientError, NotAuthorized

from homeassistant.config_entries import ConfigEntry
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
    CONF_ALLOW_EA,
    DEFAULT_SCAN_INTERVAL,
    DEVICES_THAT_ADOPT,
    DOMAIN,
    MIN_REQUIRED_PROTECT_V,
    OUTDATED_LOG_MESSAGE,
    PLATFORMS,
)
from .data import ProtectData, async_ufp_instance_for_config_entry_ids
from .discovery import async_start_discovery
from .migrate import async_migrate_data
from .services import async_cleanup_services, async_setup_services
from .utils import (
    _async_unifi_mac_from_hass,
    async_create_api_client,
    async_get_devices,
)
from .views import ThumbnailProxyView, VideoProxyView

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the UniFi Protect."""
    # Only start discovery once regardless of how many entries they have
    async_start_discovery(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the UniFi Protect config entries."""
    protect = async_create_api_client(hass, entry)
    _LOGGER.debug("Connect to UniFi Protect")
    data_service = ProtectData(hass, protect, SCAN_INTERVAL, entry)

    try:
        nvr_info = await protect.get_nvr()
    except NotAuthorized as err:
        raise ConfigEntryAuthFailed(err) from err
    except (asyncio.TimeoutError, ClientError, ServerDisconnectedError) as err:
        raise ConfigEntryNotReady from err

    if nvr_info.version < MIN_REQUIRED_PROTECT_V:
        _LOGGER.error(
            OUTDATED_LOG_MESSAGE,
            nvr_info.version,
            MIN_REQUIRED_PROTECT_V,
        )
        return False

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=nvr_info.mac)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data_service
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, data_service.async_stop)
    )

    if (
        not entry.options.get(CONF_ALLOW_EA, False)
        and await nvr_info.get_is_prerelease()
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "ea_warning",
            is_fixable=True,
            is_persistent=True,
            learn_more_url="https://www.home-assistant.io/integrations/unifiprotect#about-unifi-early-access",
            severity=IssueSeverity.WARNING,
            translation_key="ea_warning",
            translation_placeholders={"version": str(nvr_info.version)},
            data={"entry_id": entry.entry_id},
        )

    try:
        await _async_setup_entry(hass, entry, data_service)
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
            ir.async_delete_issue(hass, DOMAIN, "ea_warning")
            _LOGGER.exception("Error setting up UniFi Protect integration: %s", err)
        raise

    return True


async def _async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, data_service: ProtectData
) -> None:
    await async_migrate_data(hass, entry, data_service.api)

    await data_service.async_setup()
    if not data_service.last_update_success:
        raise ConfigEntryNotReady

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    hass.http.register_view(ThumbnailProxyView(hass))
    hass.http.register_view(VideoProxyView(hass))


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload UniFi Protect config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: ProtectData = hass.data[DOMAIN][entry.entry_id]
        await data.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id)
        async_cleanup_services(hass)

    return bool(unload_ok)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove ufp config entry from a device."""
    unifi_macs = {
        _async_unifi_mac_from_hass(connection[1])
        for connection in device_entry.connections
        if connection[0] == dr.CONNECTION_NETWORK_MAC
    }
    api = async_ufp_instance_for_config_entry_ids(hass, {config_entry.entry_id})
    assert api is not None
    if api.bootstrap.nvr.mac in unifi_macs:
        return False
    for device in async_get_devices(api.bootstrap, DEVICES_THAT_ADOPT):
        if device.is_adopted_by_us and device.mac in unifi_macs:
            return False
    return True
