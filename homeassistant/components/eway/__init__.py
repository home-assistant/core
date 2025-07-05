"""The Eway integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_SN,
    CONF_MQTT_HOST,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_USERNAME,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import EwayDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Configuration schema for configuration.yaml
DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MQTT_HOST): cv.string,
        vol.Optional(CONF_MQTT_PORT, default=1883): cv.port,
        vol.Optional(CONF_MQTT_USERNAME): cv.string,
        vol.Optional(CONF_MQTT_PASSWORD): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_DEVICE_SN): cv.string,
        vol.Optional(CONF_DEVICE_MODEL, default="Unknown"): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Any(
            DEVICE_SCHEMA,  # Single device configuration
            vol.All(cv.ensure_list, [DEVICE_SCHEMA]),  # Multiple devices configuration
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Eway component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})

    # Check if there's configuration in configuration.yaml
    if DOMAIN not in config:
        return True

    domain_config = config[DOMAIN]

    # Handle both single device and multiple devices configuration
    if isinstance(domain_config, dict):
        # Single device configuration
        devices = [domain_config]
    else:
        # Multiple devices configuration (list)
        devices = domain_config

    # Store YAML configurations for later use
    hass.data[DOMAIN]["yaml_configs"] = devices

    # Create config entries for each device if they don't exist
    for device_config in devices:
        # Create a unique identifier for this device
        device_identifier = (
            f"{device_config[CONF_DEVICE_ID]}_{device_config[CONF_DEVICE_SN]}"
        )

        # Check if config entry already exists
        existing_entries = [
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.unique_id == device_identifier
        ]

        if not existing_entries:
            # Create new config entry from YAML configuration
            _LOGGER.info(
                "Creating config entry for device %s from configuration.yaml",
                device_identifier,
            )

            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data=device_config,
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eway from a config entry."""
    coordinator = EwayDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in entry.runtime_data (modern approach)
    entry.runtime_data = coordinator

    # Keep backward compatibility with hass.data storage
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
