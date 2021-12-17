"""Support for Luftdaten stations."""
from __future__ import annotations

import logging

from luftdaten import Luftdaten
from luftdaten.exceptions import LuftdatenError

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    PERCENTAGE,
    PRESSURE_PA,
    TEMP_CELSIUS,
    Platform,
)
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .config_flow import duplicate_stations
from .const import CONF_SENSOR_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_LUFTDATEN = "luftdaten"
DATA_LUFTDATEN_CLIENT = "data_luftdaten_client"
DATA_LUFTDATEN_LISTENER = "data_luftdaten_listener"

PLATFORMS = [Platform.SENSOR]

TOPIC_UPDATE = f"{DOMAIN}_data_update"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        icon="mdi:water-percent",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        icon="mdi:arrow-down-bold",
        native_unit_of_measurement=PRESSURE_PA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="pressure_at_sealevel",
        name="Pressure at sealevel",
        icon="mdi:download",
        native_unit_of_measurement=PRESSURE_PA,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    SensorEntityDescription(
        key="P1",
        name="PM10",
        icon="mdi:thought-bubble",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
    SensorEntityDescription(
        key="P2",
        name="PM2.5",
        icon="mdi:thought-bubble-outline",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


@callback
def _async_fixup_sensor_id(hass, config_entry, sensor_id):
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, CONF_SENSOR_ID: int(sensor_id)}
    )


async def async_setup_entry(hass, config_entry):
    """Set up Luftdaten as config entry."""
    hass.data.setdefault(
        DOMAIN,
        {
            DATA_LUFTDATEN_CLIENT: {},
            DATA_LUFTDATEN_LISTENER: {},
        },
    )

    if not isinstance(config_entry.data[CONF_SENSOR_ID], int):
        _async_fixup_sensor_id(hass, config_entry, config_entry.data[CONF_SENSOR_ID])

    if (
        config_entry.data[CONF_SENSOR_ID] in duplicate_stations(hass)
        and config_entry.source == SOURCE_IMPORT
    ):
        _LOGGER.warning(
            "Removing duplicate sensors for station %s",
            config_entry.data[CONF_SENSOR_ID],
        )
        hass.async_create_task(hass.config_entries.async_remove(config_entry.entry_id))
        return False

    try:
        luftdaten = LuftDatenData(
            Luftdaten(config_entry.data[CONF_SENSOR_ID]),
            config_entry.data.get(CONF_SENSORS, {}).get(
                CONF_MONITORED_CONDITIONS, SENSOR_KEYS
            ),
        )
        await luftdaten.async_update()
        hass.data[DOMAIN][DATA_LUFTDATEN_CLIENT][config_entry.entry_id] = luftdaten
    except LuftdatenError as err:
        raise ConfigEntryNotReady from err

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    async def refresh_sensors(event_time):
        """Refresh Luftdaten data."""
        await luftdaten.async_update()
        async_dispatcher_send(hass, TOPIC_UPDATE)

    hass.data[DOMAIN][DATA_LUFTDATEN_LISTENER][
        config_entry.entry_id
    ] = async_track_time_interval(
        hass,
        refresh_sensors,
        hass.data[DOMAIN].get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an Luftdaten config entry."""
    remove_listener = hass.data[DOMAIN][DATA_LUFTDATEN_LISTENER].pop(
        config_entry.entry_id
    )
    remove_listener()

    hass.data[DOMAIN][DATA_LUFTDATEN_CLIENT].pop(config_entry.entry_id)

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


class LuftDatenData:
    """Define a generic Luftdaten object."""

    def __init__(self, client, sensor_conditions):
        """Initialize the Luftdata object."""
        self.client = client
        self.data = {}
        self.sensor_conditions = sensor_conditions

    async def async_update(self):
        """Update sensor/binary sensor data."""
        try:
            await self.client.get_data()

            if self.client.values:
                self.data[DATA_LUFTDATEN] = self.client.values
                self.data[DATA_LUFTDATEN].update(self.client.meta)

        except LuftdatenError:
            _LOGGER.error("Unable to retrieve data from luftdaten.info")
