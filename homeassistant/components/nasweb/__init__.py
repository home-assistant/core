"""The NASweb integration."""
from __future__ import annotations

import logging

from webio_api import WebioAPI

from homeassistant.components.http import ApiConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER, NASWEB_CONFIG_URL, NOTIFY_COORDINATOR
from .coordinator import NASwebCoordinator, NotificationCoordinator
from .helper import get_hass_address_from_entry, initialize_notification_coordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NASweb from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    notify_coordinator = hass.data[DOMAIN].get(NOTIFY_COORDINATOR)
    if notify_coordinator is None:
        notify_coordinator = initialize_notification_coordinator(hass)
        if notify_coordinator is None:
            _LOGGER.error("Failed to initialize coordinator")
            return False
        hass.data[DOMAIN][NOTIFY_COORDINATOR] = notify_coordinator

    webio_api = WebioAPI(
        entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    if not await webio_api.check_connection():
        _LOGGER.error("WebioAPI.check_connection: failed")
        return False
    if not await webio_api.refresh_device_info():
        _LOGGER.error("WebioAPI.refresh_device_info: failed")
        return False
    webio_serial = webio_api.get_serial_number()
    if webio_serial is None:
        _LOGGER.error("WebIO serial number is not available")
        return False

    coordinator = NASwebCoordinator(
        hass, webio_api, name=f"NASweb[{webio_api.get_name()}]"
    )
    hass.data[DOMAIN][entry.entry_id] = coordinator
    notify_coordinator.add_coordinator(webio_serial, coordinator)

    hass_address = get_hass_address_from_entry(hass, entry.data)
    if hass_address is None:
        _LOGGER.error("Cannot determine hass address for webio")
        return False
    if not await webio_api.status_subscription(hass_address, True):
        _LOGGER.error("Failed to subscribe for status updates from webio")
        return False

    if not await notify_coordinator.check_connection(webio_serial):
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
        configuration_url=NASWEB_CONFIG_URL.replace("[host]", entry.data[CONF_HOST]),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        notify_coordinator: NotificationCoordinator = hass.data[DOMAIN].get(
            NOTIFY_COORDINATOR
        )
        coordinator: NASwebCoordinator = hass.data[DOMAIN].get(entry.entry_id)
        if coordinator is not None:
            serial = coordinator.webio_api.get_serial_number()
            if notify_coordinator is not None and serial is not None:
                notify_coordinator.remove_coordinator(serial)
                hass_address = get_hass_address_from_entry(hass, entry.data)
                if hass_address is None:
                    api_config: ApiConfig | None = hass.config.api
                    if api_config is not None:
                        hass_address = f"{api_config.host}:{api_config.port}"
                if hass_address is not None:
                    await coordinator.webio_api.status_subscription(hass_address, False)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
