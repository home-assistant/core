"""The NASweb integration."""
from __future__ import annotations

import logging

from webio_api import WebioAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER, NASWEB_CONFIG_URL
from .coordinator import NASwebCoordinator
from .helper import (
    deinitialize_nasweb_data_if_empty,
    get_integration_webhook_url,
    initialize_nasweb_data,
)
from .nasweb_data import NASwebData

PLATFORMS: list[Platform] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NASweb from a config entry."""

    hass.data.setdefault(DOMAIN, NASwebData())
    nasweb_data: NASwebData = hass.data[DOMAIN]
    if not nasweb_data.is_initialized():
        initialize_nasweb_data(hass)

    webio_api = WebioAPI(
        entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    if not await webio_api.check_connection():
        raise ConfigEntryNotReady(f"[{entry.data[CONF_HOST]}] Check connection failed")
    if not await webio_api.refresh_device_info():
        _LOGGER.error("[%s] Refresh device info failed", entry.data[CONF_HOST])
        return False
    webio_serial = webio_api.get_serial_number()
    if webio_serial is None:
        _LOGGER.error("[%s] Serial number not available", entry.data[CONF_HOST])
        return False

    coordinator = NASwebCoordinator(
        hass, webio_api, name=f"NASweb[{webio_api.get_name()}]"
    )
    nasweb_data.entries_coordinators[entry.entry_id] = coordinator
    nasweb_data.notify_coordinator.add_coordinator(webio_serial, coordinator)

    webhook_url = get_integration_webhook_url(hass)
    if not await webio_api.status_subscription(webhook_url, True):
        _LOGGER.error("Failed to subscribe for status updates from webio")
        return False

    if not await nasweb_data.notify_coordinator.check_connection(webio_serial):
        _LOGGER.error(
            "Wasn't able to confirm connection with webio. Check form data and try again"
        )
        return False

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, webio_serial)},
        manufacturer=MANUFACTURER,
        name=webio_api.get_name(),
        configuration_url=NASWEB_CONFIG_URL.format(host=entry.data[CONF_HOST]),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        nasweb_data: NASwebData = hass.data[DOMAIN]
        coordinator: NASwebCoordinator = nasweb_data.entries_coordinators.pop(
            entry.entry_id
        )
        webhook_url = get_integration_webhook_url(hass)
        await coordinator.webio_api.status_subscription(webhook_url, False)
        serial = coordinator.webio_api.get_serial_number()
        if serial is not None:
            nasweb_data.notify_coordinator.remove_coordinator(serial)
        deinitialize_nasweb_data_if_empty(hass)

    return unload_ok
