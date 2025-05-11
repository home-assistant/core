"""The Qbus integration."""

import logging

from homeassistant.components.mqtt import async_wait_for_mqtt_client
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .coordinator import (
    QBUS_KEY,
    QbusConfigCoordinator,
    QbusConfigEntry,
    QbusControllerCoordinator,
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Qbus integration.

    We set up a single coordinator for managing Qbus config updates. The
    config update contains the configuration for all controllers (and
    config entries). This avoids having each device requesting and managing
    the config on its own.
    """
    _LOGGER.debug("Loading integration")

    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration not available")
        return False

    config_coordinator = QbusConfigCoordinator.get_or_create(hass)
    await config_coordinator.async_subscribe_to_config()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: QbusConfigEntry) -> bool:
    """Set up Qbus from a config entry."""
    _LOGGER.debug("%s - Loading entry", entry.unique_id)

    if not await async_wait_for_mqtt_client(hass):
        _LOGGER.error("MQTT integration not available")
        raise ConfigEntryNotReady("MQTT integration not available")

    coordinator = QbusControllerCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Get current config
    config = await QbusConfigCoordinator.get_or_create(
        hass
    ).async_get_or_request_config()

    # Update the controller config
    if config:
        await coordinator.async_update_controller_config(config)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: QbusConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("%s - Unloading entry", entry.unique_id)

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.shutdown()
        _cleanup(hass, entry)

    return unload_ok


def _cleanup(hass: HomeAssistant, entry: QbusConfigEntry) -> None:
    """Shutdown if no more entries are loaded."""
    if not hass.config_entries.async_loaded_entries(DOMAIN) and (
        config_coordinator := hass.data.get(QBUS_KEY)
    ):
        config_coordinator.shutdown()
