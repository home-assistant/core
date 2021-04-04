"""The sma integration."""
import asyncio
from datetime import timedelta
import logging

import pysma

from homeassistant.config_entries import ConfigEntry
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
    PYSMA_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up sma from a config entry."""
    # Init all default sensors
    sensor_def = pysma.Sensors()

    if entry.source == "import":
        # Add sensors from the custom config
        # Supports deprecated yaml config from platform setup
        sensor_def.add(
            [
                pysma.Sensor(
                    o[CONF_KEY], n, o[CONF_UNIT], o[CONF_FACTOR], o.get(CONF_PATH)
                )
                for n, o in entry.data.get(CONF_CUSTOM).items()
            ]
        )

        # When CONF_SENSORS is set, only enable sensors in config
        # Supports deprecated yaml config from platform setup
        config_sensors = entry.data.get(CONF_SENSORS)
        if config_sensors:
            # find and replace sensors removed from pysma
            for sensor in config_sensors.copy():
                if sensor in pysma.LEGACY_MAP:
                    config_sensors.remove(sensor)
                    config_sensors.append(pysma.LEGACY_MAP[sensor]["new_sensor"])

            for s in sensor_def:
                s.enabled = s.name in config_sensors

        # Create list of all possible sensor names
        possible_sensors = list(
            set(config_sensors + [s.name for s in sensor_def] + list(pysma.LEGACY_MAP))
        )

        entity_registry = er.async_get(hass)

        # Find entity_id using previous format of unique ID and change to new unique ID
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

            entity_id = entity_registry.async_get_entity_id(
                "sensor", "sma", f"sma-{original_key}-{sensor}"
            )
            if entity_id:
                new_unique_id = (
                    f"{entry.unique_id}-{pysma_sensor.key}_{pysma_sensor.key_idx}"
                )
                entity_registry.async_update_entity(
                    entity_id, new_unique_id=new_unique_id
                )

    # Init the SMA interface
    protocol = "https" if entry.data.get(CONF_SSL) else "http"
    url = f"{protocol}://{entry.data.get(CONF_HOST)}"
    verify_ssl = entry.data.get(CONF_VERIFY_SSL)
    group = entry.data.get(CONF_GROUP)
    password = entry.data.get(CONF_PASSWORD)

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    sma = pysma.SMA(session, url, password, group)

    # Ensure we logout on shutdown
    async def async_close_session(event):
        """Close the session."""
        await sma.close_session()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_close_session)

    async def async_update_data():
        """Update the used SMA sensors."""
        values = await sma.read(sensor_def)
        if not values:
            raise UpdateFailed

    interval = entry.options.get(CONF_SCAN_INTERVAL) or timedelta(
        seconds=DEFAULT_SCAN_INTERVAL
    )

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="sma",
        update_method=async_update_data,
        update_interval=interval,
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        PYSMA_OBJECT: sma,
        PYSMA_COORDINATOR: coordinator,
        PYSMA_SENSORS: sensor_def,
    }

    await coordinator.async_config_entry_first_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
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
        sma = hass.data[DOMAIN][entry.entry_id][PYSMA_OBJECT]
        await sma.close_session()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
