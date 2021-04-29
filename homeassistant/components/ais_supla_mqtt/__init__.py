"""Support for AIS SUPLA MQTT"""
import asyncio
import logging
import os

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

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.info("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        # save mqtt connection info
        # 1. check if mosquitto.conf exists
        if not os.path.isfile(
            "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf"
        ):
            _LOGGER.error("No mosquitto.conf file exit")
            return False

        # 2. configuration file exist, check if we have bridge definition
        bridge_settings = "connection bridge-" + ais_global.get_sercure_android_id_dom()
        conf_file = open(
            "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf"
        )
        if bridge_settings in conf_file:
            _LOGGER.error("Connection bridge exists in mosquitto.conf, exit")
            return False

        # 3. configuration add bridge definition
        mqtt_settings = config_entry.data
        with open(
            "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf", "w"
        ) as conf_file:
            # save connection in file
            conf_file.write("# AIS Config file for mosquitto\n")
            conf_file.write("listener 1883 0.0.0.0\n")
            conf_file.write("allow_anonymous true\n")
            conf_file.write("\n")
            conf_file.write(bridge_settings + "\n")
            conf_file.write(
                "address "
                + mqtt_settings["host"]
                + ":"
                + str(mqtt_settings["port"])
                + "\n"
            )
            conf_file.write("topic supla/# in\n")
            conf_file.write("topic homeassistant/# in\n")
            conf_file.write("topic supla/+/devices/+/channels/+/execute_action out\n")
            conf_file.write("topic supla/+/devices/+/channels/+/set/+ out\n")
            conf_file.write("remote_username " + mqtt_settings["username"] + "\n")
            conf_file.write("remote_password " + mqtt_settings["password"] + "\n")
            conf_file.write(
                "bridge_cafile /data/data/pl.sviete.dom/files/usr/etc/tls/cert.pem\n"
            )
        # restart mqtt broker
        await hass.services.async_call(
            "ais_shell_command", "restart_pm2_service", {"service": "mqtt"}
        )
        config_entry.version = 2

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # 1. check if mosquitto.conf exists
    if not os.path.isfile(
        "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf"
    ):
        _LOGGER.error("No mosquitto.conf file exit")
        return False
    # 2. remove settings from file
    with open(
        "/data/data/pl.sviete.dom/files/usr/etc/mosquitto/mosquitto.conf", "w"
    ) as conf_file:
        conf_file.write("# AIS Config file for mosquitto\n")
        conf_file.write("listener 1883 0.0.0.0\n")
        conf_file.write("allow_anonymous true\n")

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
