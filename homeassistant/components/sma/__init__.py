"""The sma integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import pysma

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryNotReady
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_SSL,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CUSTOM,
    CONF_FACTOR,
    CONF_GROUP,
    CONF_KEY,
    CONF_UNIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    PYSMA_COORDINATOR,
    PYSMA_OBJECT,
    PYSMA_REMOVE_LISTENER,
    PYSMA_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


def _parse_legacy_options(entry: ConfigEntry, sensor_def: pysma.Sensors) -> list[str]:
    """Parse legacy configuration options.

    This will parse the legacy CONF_SENSORS and CONF_CUSTOM configuration options
    to support deprecated yaml config from platform setup.
    """

    # Add sensors from the custom config
    sensor_def.add(
        [
            pysma.Sensor(o[CONF_KEY], n, o[CONF_UNIT], o[CONF_FACTOR], o.get(CONF_PATH))
            for n, o in entry.data.get(CONF_CUSTOM).items()
        ]
    )

    # Parsing of sensors configuration
    config_sensors = entry.data.get(CONF_SENSORS)
    if not config_sensors:
        return []

    # Support import of legacy config that should have been removed from 0.99, but was still functional
    # See also #25880 and #26306. Functional support was dropped in #48003
    if isinstance(config_sensors, dict):
        config_sensors_list = []

        for name, attr in config_sensors.items():
            config_sensors_list.append(name)
            config_sensors_list.extend(attr)

        config_sensors = config_sensors_list

    # Find and replace sensors removed from pysma
    # This only alters the config, the actual sensor migration takes place in _migrate_old_unique_ids
    for sensor in config_sensors.copy():
        if sensor in pysma.LEGACY_MAP:
            config_sensors.remove(sensor)
            config_sensors.append(pysma.LEGACY_MAP[sensor]["new_sensor"])

    # Only sensors from config should be enabled
    for sensor in sensor_def:
        sensor.enabled = sensor.name in config_sensors

    return config_sensors


def _migrate_old_unique_ids(
    hass: HomeAssistant,
    entry: ConfigEntry,
    sensor_def: pysma.Sensors,
    config_sensors: list[str],
) -> None:
    """Migrate legacy sensor entity_id format to new format."""
    entity_registry = er.async_get(hass)

    # Create list of all possible sensor names
    possible_sensors = set(
        config_sensors + [s.name for s in sensor_def] + list(pysma.LEGACY_MAP)
    )

    for sensor in possible_sensors:
        if sensor in sensor_def:
            pysma_sensor = sensor_def[sensor]
            original_key = pysma_sensor.key
        elif sensor in pysma.LEGACY_MAP:
            # If sensor was removed from pysma we will remap it to the new sensor
            legacy_sensor = pysma.LEGACY_MAP[sensor]
            pysma_sensor = sensor_def[legacy_sensor["new_sensor"]]
            original_key = legacy_sensor["old_key"]
        else:
            _LOGGER.error("%s does not exist", sensor)
            continue

        # Find entity_id using previous format of unique ID
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "sma", f"sma-{original_key}-{sensor}"
        )

        if not entity_id:
            continue

        # Change unique_id to new format using the device serial in entry.unique_id
        new_unique_id = f"{entry.unique_id}-{pysma_sensor.key}_{pysma_sensor.key_idx}"
        entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up sma from a config entry."""
    # Init all default sensors
    sensor_def = pysma.Sensors()

    if entry.source == SOURCE_IMPORT:
        config_sensors = _parse_legacy_options(entry, sensor_def)
        _migrate_old_unique_ids(hass, entry, sensor_def, config_sensors)

    # Init the SMA interface
    protocol = "https" if entry.data[CONF_SSL] else "http"
    url = f"{protocol}://{entry.data[CONF_HOST]}"
    verify_ssl = entry.data[CONF_VERIFY_SSL]
    group = entry.data[CONF_GROUP]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    sma = pysma.SMA(session, url, password, group)

    # Define the coordinator
    async def async_update_data():
        """Update the used SMA sensors."""
        values = await sma.read(sensor_def)
        if not values:
            raise UpdateFailed

    interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sma",
        update_method=async_update_data,
        update_interval=interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await sma.close_session()
        raise

    # Ensure we logout on shutdown
    async def async_close_session(event):
        """Close the session."""
        await sma.close_session()

    remove_stop_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_close_session
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        PYSMA_OBJECT: sma,
        PYSMA_COORDINATOR: coordinator,
        PYSMA_SENSORS: sensor_def,
        PYSMA_REMOVE_LISTENER: remove_stop_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data[PYSMA_OBJECT].close_session()
        data[PYSMA_REMOVE_LISTENER]()

    return unload_ok
