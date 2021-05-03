"""Support for AIS SUPLA MQTT"""
import asyncio
import logging

from homeassistant.components.ais_dom import ais_global
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the AI Speaker integration."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up SUPLA MQTT from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = entry

    # after reload from app the the async_unload_entry is called
    # check if we still have bridge definition
    include_mqtt_dir = (
        "include_mqtt /data/data/pl.sviete.dom/files/home/AIS/.dom/mqtt_conf.d"
    )
    conf_file = open("/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf")
    if include_mqtt_dir not in conf_file:
        _LOGGER.info("Connection bridge not exists in mosquitto.conf, reload")
        mqtt_broker_settings = entry.data.copy()
        mqtt_broker_settings["file_config_name"] = "supla.conf"
        ais_global.save_ais_mqtt_connection_settings(mqtt_broker_settings)
        # restart mqtt broker
        await hass.services.async_call(
            "ais_shell_command", "restart_pm2_service", {"service": "mqtt"}
        )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    if config_entry.version < 3:
        # save mqtt configuration add bridge definition
        mqtt_broker_settings = config_entry.data.copy()
        mqtt_broker_settings["file_config_name"] = "supla.conf"
        ais_global.save_ais_mqtt_connection_settings(mqtt_broker_settings)

        # restart mqtt broker
        await hass.services.async_call(
            "ais_shell_command", "restart_pm2_service", {"service": "mqtt"}
        )
        config_entry.version = 3

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # remove mqtt bridge settings
    ais_global.save_ais_mqtt_connection_settings(None)

    # restart mqtt broker
    await hass.services.async_call(
        "ais_shell_command", "restart_pm2_service", {"service": "mqtt"}
    )
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
