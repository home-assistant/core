"""The NASweb integration."""
from __future__ import annotations

import logging

from webio_api import WebioAPI
from webio_api.api_client import AuthError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .config_flow import MissingNASwebData
from .const import (
    DOMAIN,
    DOMAIN_DISPLAY_NAME,
    ISSUE_INTERNAL_ERROR,
    ISSUE_INVALID_AUTHENTICATION,
    ISSUE_NO_STATUS_UPDATE,
    MANUFACTURER,
    NASWEB_CONFIG_URL,
)
from .coordinator import NASwebCoordinator
from .nasweb_data import NASwebData

PLATFORMS: list[Platform] = [Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NASweb from a config entry."""

    if DOMAIN not in hass.data:
        data = NASwebData()
        data.initialize(hass)
        hass.data[DOMAIN] = data
    nasweb_data: NASwebData = hass.data[DOMAIN]

    webio_api = WebioAPI(
        entry.data[CONF_HOST], entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    try:
        if not await webio_api.check_connection():
            raise ConfigEntryNotReady(
                f"[{entry.data[CONF_HOST]}] Check connection failed"
            )
        if not await webio_api.refresh_device_info():
            _LOGGER.error("[%s] Refresh device info failed", entry.data[CONF_HOST])
            raise MissingNASwebData
        webio_serial = webio_api.get_serial_number()
        if webio_serial is None:
            _LOGGER.error("[%s] Serial number not available", entry.data[CONF_HOST])
            raise MissingNASwebData

        coordinator = NASwebCoordinator(
            hass, webio_api, name=f"NASweb[{webio_api.get_name()}]"
        )
        nasweb_data.entries_coordinators[entry.entry_id] = coordinator
        nasweb_data.notify_coordinator.add_coordinator(webio_serial, coordinator)

        webhook_url = nasweb_data.get_webhook_url(hass)
        if webhook_url is None:
            _LOGGER.error("Cannot pass Home Assistant url to NASweb device")
            raise MissingNASwebData
        if not await webio_api.status_subscription(webhook_url, True):
            _LOGGER.error("Failed to subscribe for status updates from webio")
            raise MissingNASwebData
    except AuthError:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_INVALID_AUTHENTICATION}_{entry.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_INVALID_AUTHENTICATION,
            translation_placeholders={
                "domain_name": DOMAIN_DISPLAY_NAME,
                "device_name": entry.title,
            },
        )
        return False
    except MissingNASwebData:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_INTERNAL_ERROR}_{entry.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_INTERNAL_ERROR,
            translation_placeholders={
                "domain_name": DOMAIN_DISPLAY_NAME,
                "device_name": entry.title,
            },
        )
        return False
    ir.async_delete_issue(
        hass, DOMAIN, f"{ISSUE_INVALID_AUTHENTICATION}_{entry.entry_id}"
    )
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_INTERNAL_ERROR}_{entry.entry_id}")
    if not await nasweb_data.notify_coordinator.check_connection(webio_serial):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{ISSUE_NO_STATUS_UPDATE}_{entry.entry_id}",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_NO_STATUS_UPDATE,
            translation_placeholders={
                "domain_name": DOMAIN_DISPLAY_NAME,
                "device_name": entry.title,
            },
        )
        return False
    ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_NO_STATUS_UPDATE}_{entry.entry_id}")
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
        ir.async_delete_issue(
            hass, DOMAIN, f"{ISSUE_INVALID_AUTHENTICATION}_{entry.entry_id}"
        )
        ir.async_delete_issue(hass, DOMAIN, f"{ISSUE_INTERNAL_ERROR}_{entry.entry_id}")
        ir.async_delete_issue(
            hass, DOMAIN, f"{ISSUE_NO_STATUS_UPDATE}_{entry.entry_id}"
        )
        nasweb_data: NASwebData = hass.data[DOMAIN]
        coordinator: NASwebCoordinator = nasweb_data.entries_coordinators.pop(
            entry.entry_id
        )
        webhook_url = nasweb_data.get_webhook_url(hass)
        if webhook_url is not None:
            await coordinator.webio_api.status_subscription(webhook_url, False)
        serial = coordinator.webio_api.get_serial_number()
        if serial is not None:
            nasweb_data.notify_coordinator.remove_coordinator(serial)
        if nasweb_data.can_be_deinitialized():
            nasweb_data.deinitialize(hass)
            hass.data.pop(DOMAIN)

    return unload_ok
