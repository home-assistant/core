"""DayBetter Services integration for Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, PLATFORMS
from .daybetter_api import DayBetterApi
from .mqtt_manager import DayBetterMQTTManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up DayBetter Services from a config entry."""
    _LOGGER.debug("Setting up DayBetter Services integration")

    # Initialize the API client
    token = entry.data.get("token")
    if not token:
        _LOGGER.error("No token found in config entry")
        return False
    api = DayBetterApi(hass, token)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
    }

    # Fetch devices and store them
    devices = await api.fetch_devices()
    hass.data[DOMAIN][entry.entry_id]["devices"] = devices

    # Initialize MQTT manager (but don't connect yet)
    mqtt_manager = DayBetterMQTTManager(hass, entry)
    hass.data[DOMAIN][entry.entry_id]["mqtt_manager"] = mqtt_manager

    # Setup services (register only on first setup)
    if not hass.data[DOMAIN].get("services_registered", False):
        await async_setup_services(hass, entry)
        hass.data[DOMAIN]["services_registered"] = True

    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Finally try to connect to MQTT broker (need to get certificate URL first)
    _LOGGER.info("Attempting to connect to DayBetter MQTT broker...")
    try:
        mqtt_connected = await mqtt_manager.async_connect()
        if mqtt_connected:
            _LOGGER.info("✅ Successfully connected to DayBetter MQTT broker")
        else:
            _LOGGER.warning(
                "⚠️ Unable to connect to DayBetter MQTT broker, devices may not update in real-time"
            )
    except Exception as e:
        _LOGGER.error("Exception occurred during MQTT connection: %s", str(e))

    return True


async def trigger_mqtt_connection(
    hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall
) -> None:
    """Trigger MQTT connection."""
    mqtt_manager = hass.data[DOMAIN][entry.entry_id]["mqtt_manager"]

    _LOGGER.info("Manually triggering MQTT connection...")
    mqtt_connected = await mqtt_manager.async_connect()
    if mqtt_connected:
        _LOGGER.info("✅ MQTT connection successful")
    else:
        _LOGGER.error("❌ MQTT connection failed")


async def refresh_devices(
    hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall
) -> None:
    """Refresh device list."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    devices = await api.fetch_devices()
    hass.data[DOMAIN][entry.entry_id]["devices"] = devices


async def get_mqtt_config(
    hass: HomeAssistant, entry: ConfigEntry, call: ServiceCall
) -> None:
    """Get MQTT configuration information."""
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    _LOGGER.info("Getting MQTT configuration information...")
    try:
        mqtt_config = await api.fetch_mqtt_config()
        _LOGGER.info("MQTT configuration: %s", mqtt_config)
    except Exception as e:
        _LOGGER.error("Failed to get MQTT configuration: %s", str(e))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading DayBetter Services integration")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            # Remove services if no entries left
            _LOGGER.debug("Removing DayBetter Services integration services")
            hass.services.async_remove(DOMAIN, "trigger_mqtt_connection")
            hass.services.async_remove(DOMAIN, "refresh_devices")

    return unload_ok


async def async_setup_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Setup services."""
    # Register trigger MQTT connection service
    hass.services.async_register(
        DOMAIN,
        "trigger_mqtt_connection",
        lambda call: trigger_mqtt_connection(hass, entry, call),
    )

    # Register refresh devices service
    hass.services.async_register(
        DOMAIN, "refresh_devices", lambda call: refresh_devices(hass, entry, call)
    )

    # Register get MQTT config service
    hass.services.async_register(
        DOMAIN, "get_mqtt_config", lambda call: get_mqtt_config(hass, entry, call)
    )
