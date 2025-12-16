"""The ZhongHong HVAC integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from zhong_hong_hvac.hub import ZhongHongGateway

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_GATEWAY_ADDRESS, DEFAULT_GATEWAY_ADDRESS, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(
                    CONF_GATEWAY_ADDRESS, default=DEFAULT_GATEWAY_ADDRESS
                ): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ZhongHong HVAC component from YAML."""
    if DOMAIN not in config:
        return True

    yaml_config = config[DOMAIN]

    existing_entries = hass.config_entries.async_entries(DOMAIN)
    existing_hosts = {entry.data[CONF_HOST] for entry in existing_entries}

    if yaml_config and yaml_config[CONF_HOST] not in existing_hosts:
        _LOGGER.info("Importing ZhongHong HVAC configuration from configuration.yaml")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=yaml_config,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZhongHong HVAC from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    gw_addr = entry.data[CONF_GATEWAY_ADDRESS]

    hub = ZhongHongGateway(host, port, gw_addr)

    _LOGGER.debug("Discovering ZhongHong devices")
    devices_discovered = await hass.async_add_executor_job(hub.discovery_ac)

    if not devices_discovered:
        _LOGGER.error("No ZhongHong devices found. Cannot set up integration")
        await hass.async_add_executor_job(hub.stop_listen)
        return False

    _LOGGER.debug("Found %d devices", len(devices_discovered))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "devices": devices_discovered,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def _start_hub():
        """Start the hub socket and query status of all devices."""
        _LOGGER.debug("Starting ZhongHong listener and querying all devices")
        hub.start_listen()
        hub.query_all_status()

    await hass.async_add_executor_job(_start_hub)

    async def async_stop_hub(event=None):
        """Asynchronous wrapper to safely stop the hub."""
        _LOGGER.debug("Stopping ZhongHong listener")
        await hass.async_add_executor_job(hub.stop_listen)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_hub)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        hub = entry_data.get("hub")
        if hub:
            await hass.async_add_executor_job(hub.stop_listen)

    return unload_ok
