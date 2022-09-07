"""UniFi Protect Platform."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiohttp import CookieJar
from aiohttp.client_exceptions import ServerDisconnectedError
from pyunifiprotect import ProtectApiClient
from pyunifiprotect.exceptions import ClientError, NotAuthorized

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_ALL_UPDATES,
    CONF_OVERRIDE_CHOST,
    DEFAULT_SCAN_INTERVAL,
    DEVICES_FOR_SUBSCRIBE,
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
from .utils import _async_unifi_mac_from_hass, async_get_devices
from .views import ThumbnailProxyView, VideoProxyView

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the UniFi Protect config entries."""

    async_start_discovery(hass)
    session = async_create_clientsession(hass, cookie_jar=CookieJar(unsafe=True))
    protect = ProtectApiClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
        session=session,
        subscribed_models=DEVICES_FOR_SUBSCRIBE,
        override_connection_host=entry.options.get(CONF_OVERRIDE_CHOST, False),
        ignore_stats=not entry.options.get(CONF_ALL_UPDATES, False),
        ignore_unadopted=False,
    )
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

    await async_migrate_data(hass, entry, protect)
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=nvr_info.mac)

    await data_service.async_setup()
    if not data_service.last_update_success:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data_service
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)
    hass.http.register_view(ThumbnailProxyView(hass))
    hass.http.register_view(VideoProxyView(hass))

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, data_service.async_stop)
    )

    return True


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
