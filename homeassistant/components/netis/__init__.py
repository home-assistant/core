"""The Netis Router integration.

This module is the entry point for the Netis Router integration. It sets up
the DataUpdateCoordinator and forwards setup to all platform entities.

Architecture overview
---------------------
1. ``async_setup_entry`` creates a :class:`NetisCoordinator` which polls the
   router on a configurable interval (default 30 s).
2. The coordinator stores a :class:`NetisClient` that handles authentication
   (AES-128-CBC encrypted password) and all ubus JSON-RPC communication.
3. On each poll, ``NetisClient.gather()`` fetches system info, connected
   devices, WAN status, LTE signal, WiFi configuration and LED state
   concurrently, returning a typed :class:`NetisData` snapshot.
4. Platform entities (device_tracker, sensor, binary_sensor, button, switch,
   select) read from the coordinator's cached snapshot and are automatically
   refreshed on each successful poll.

The integration uses the modern ``runtime_data`` pattern (HA 2024.8+) instead
of ``hass.data`` for storing the coordinator reference.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv

from .api import NetisError
from .const import DOMAIN, PLATFORMS
from .coordinator import NetisCoordinator

_LOGGER = logging.getLogger(__name__)

# Type alias: each config entry carries its coordinator at runtime.
NetisConfigEntry = ConfigEntry[NetisCoordinator]

# Service schemas (matched against services.yaml field definitions).
SEND_SMS_SCHEMA = vol.Schema(
    {
        vol.Required("phone"): cv.string,
        vol.Required("message"): cv.string,
    }
)
SET_SPEED_LIMIT_SCHEMA = vol.Schema(
    {
        vol.Required("mac"): cv.string,
        vol.Required("down_speed", default=0): vol.Coerce(int),
        vol.Required("up_speed", default=0): vol.Coerce(int),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: NetisConfigEntry) -> bool:
    """Set up Netis Router from a config entry.

    This is called by Home Assistant when the user adds the integration via
    the UI config flow. It performs the first data fetch (which will raise
    ``ConfigEntryNotReady`` on failure so HA retries with backoff) and then
    forwards setup to all platform handlers.
    """
    coordinator = NetisCoordinator(hass, entry)
    # Fetch initial data; HA will retry setup if this fails.
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator on the entry for platform access (HA 2024.8+).
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register custom services.
    _async_register_services(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NetisConfigEntry) -> bool:
    """Unload a config entry.

    Called when the user removes the integration. Cleans up all platform
    entities and registered services associated with this entry.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Remove services when the last config entry is unloaded.
        _async_unregister_services(hass)
    return unload_ok


def _get_coordinator(hass: HomeAssistant) -> NetisCoordinator | None:
    """Return the first active Netis coordinator (single-router setup)."""
    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        if entry.runtime_data is not None:
            return entry.runtime_data  # type: ignore[return-value]
    return None


@callback
def _async_register_services(hass: HomeAssistant, entry: NetisConfigEntry) -> None:
    """Register custom services for the Netis integration."""

    async def _handle_send_sms(call: ServiceCall) -> None:
        """Service: netis.send_sms — send SMS via LTE modem."""
        coordinator = _get_coordinator(hass)
        if coordinator is None:
            _LOGGER.error("No active Netis router to send SMS")
            return
        phone = call.data["phone"]
        message = call.data["message"]
        try:
            await coordinator.client.send_sms(phone, message)
        except NetisError as err:
            _LOGGER.error("Failed to send SMS to %s: %s", phone, err)

    async def _handle_set_speed_limit(call: ServiceCall) -> None:
        """Service: netis.set_speed_limit — limit a device's bandwidth."""
        coordinator = _get_coordinator(hass)
        if coordinator is None:
            _LOGGER.error("No active Netis router to set speed limit")
            return
        mac = call.data["mac"]
        down_speed = call.data.get("down_speed", 0)
        up_speed = call.data.get("up_speed", 0)
        try:
            await coordinator.client.set_speed_limit(mac, down_speed, up_speed)
        except NetisError as err:
            _LOGGER.error("Failed to set speed limit for %s: %s", mac, err)

    # Only register once (multiple config entries share the same services).
    if not hass.services.has_service(DOMAIN, "send_sms"):
        hass.services.async_register(
            DOMAIN, "send_sms", _handle_send_sms, schema=SEND_SMS_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, "set_speed_limit"):
        hass.services.async_register(
            DOMAIN,
            "set_speed_limit",
            _handle_set_speed_limit,
            schema=SET_SPEED_LIMIT_SCHEMA,
        )


@callback
def _async_unregister_services(hass: HomeAssistant) -> None:
    """Remove custom services when no config entries remain."""
    if not hass.config_entries.async_entries(DOMAIN):
        for service in ("send_sms", "set_speed_limit"):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
