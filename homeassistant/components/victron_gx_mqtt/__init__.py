"""The victron_mqtt integration."""

from __future__ import annotations

import asyncio
import importlib.metadata
import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers.typing import ConfigType

from homeassistant.helpers import config_validation as cv

from .const import ATTR_DEVICE_ID, ATTR_METRIC_ID, ATTR_VALUE, DOMAIN, SERVICE_PUBLISH
from .hub import Hub

_LOGGER = logging.getLogger(__name__)
_VICTRON_MQTT_LOGGER = logging.getLogger("victron_mqtt")

# Config schema - this integration is config entry only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]

__all__ = ["DOMAIN"]


async def async_setup_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up services for the Victron MQTT integration."""

    # Only register services once
    if hass.services.has_service(DOMAIN, SERVICE_PUBLISH):
        return

    async def handle_publish(call: ServiceCall) -> None:
        """Handle the set_value service call."""
        metric_id = call.data.get(ATTR_METRIC_ID)
        device_id = call.data.get(ATTR_DEVICE_ID)
        value = call.data.get(ATTR_VALUE)

        if not metric_id:
            raise HomeAssistantError("metric_id is required")
        if not device_id:
            raise HomeAssistantError("device_id is required")

        # Find the hub instance
        hub: Hub = entry.runtime_data
        if hub is None:
            raise HomeAssistantError("No Victron MQTT hub found")

        hub.publish(metric_id, device_id, value)

    # Register the service
    hass.services.async_register(
        DOMAIN,
        SERVICE_PUBLISH,
        handle_publish,
    )

    _LOGGER.info("Victron MQTT services registered")


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    _LOGGER.info("Options for victron_mqtt have been updated - applying changes")
    # Reload the integration to apply changes
    await hass.config_entries.async_reload(entry.entry_id)


async def get_package_version(package_name) -> str:
    return await asyncio.get_event_loop().run_in_executor(
        None, importlib.metadata.version, package_name
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration."""
    version = getattr(hass.data["integrations"][DOMAIN], "version", 0)
    victron_mqtt_version = await get_package_version("victron_mqtt")
    _LOGGER.info(
        "Setting up victron_mqtt integration. Version: %s. victron_mqtt package version: %s",
        version,
        victron_mqtt_version,
    )

    return True


def _sync_library_logging():
    """Sync the log level of the library to match integration logging."""
    lib_level = _LOGGER.getEffectiveLevel()
    _VICTRON_MQTT_LOGGER.setLevel(lib_level)
    _VICTRON_MQTT_LOGGER.propagate = True  # Let it go through HA logging


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up victronvenus from a config entry."""
    _sync_library_logging()
    _LOGGER.debug("async_setup_entry called for entry: %s", entry.entry_id)

    hub = Hub(hass, entry)
    entry.runtime_data = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # All platforms should be set up before starting the hub
    try:
        await hub.start()
    except Exception as exc:
        _LOGGER.error(
            "Failure: hub.start() failed for entry %s: %s", entry.entry_id, exc
        )
        # Clean up partial setup to avoid double setup issues
        await async_unload_entry(hass, entry)
        raise

    # Register the update listener
    entry.async_on_unload(entry.add_update_listener(_update_listener))

    # Register services
    await async_setup_services(hass, entry)
    _LOGGER.debug("sync_setup_entry completed for entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry called for entry: %s", entry.entry_id)
    hub: Hub = entry.runtime_data
    if hub is not None:
        await hub.stop()

    # Unregister services if this is the last entry
    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        hass.services.async_remove(DOMAIN, SERVICE_PUBLISH)
        _LOGGER.info("Victron MQTT services unregistered")

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
