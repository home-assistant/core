"""Support for Solax inverter via local API."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from solax.inverter import InverterError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    },
)
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Entry setup."""
    api = hass.data[DOMAIN][entry.entry_id]
    resp = await api.get_data()
    serial = resp.serial_number
    version = resp.version
    endpoint = RealTimeDataEndpoint(hass, api)
    hass.async_add_job(endpoint.async_refresh)
    async_track_time_interval(hass, endpoint.async_refresh, SCAN_INTERVAL)
    devices = []
    for sensor, (idx, unit) in api.inverter.sensor_map().items():
        device_class = state_class = None
        if unit == "C":
            device_class = SensorDeviceClass.TEMPERATURE
            state_class = SensorStateClass.MEASUREMENT
            unit = TEMP_CELSIUS
        elif unit == "kWh":
            device_class = SensorDeviceClass.ENERGY
            state_class = SensorStateClass.TOTAL_INCREASING
        elif unit == "V":
            device_class = SensorDeviceClass.VOLTAGE
            state_class = SensorStateClass.MEASUREMENT
        elif unit == "A":
            device_class = SensorDeviceClass.CURRENT
            state_class = SensorStateClass.MEASUREMENT
        elif unit == "W":
            device_class = SensorDeviceClass.POWER
            state_class = SensorStateClass.MEASUREMENT
        elif unit == "%":
            device_class = SensorDeviceClass.BATTERY
            state_class = SensorStateClass.MEASUREMENT
        uid = f"{serial}-{idx}"
        devices.append(
            Inverter(uid, serial, version, sensor, unit, state_class, device_class)
        )
    endpoint.sensors = devices
    async_add_entities(devices)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Platform setup."""

    _LOGGER.warning(
        "Configuration of the SolaX Power platform in YAML is deprecated and "
        "will be removed in Home Assistant 2022.4; Your existing configuration "
        "has been imported into the UI automatically and can be safely removed "
        "from your configuration.yaml file"
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


class RealTimeDataEndpoint:
    """Representation of a Sensor."""

    def __init__(self, hass, api):
        """Initialize the sensor."""
        self.hass = hass
        self.api = api
        self.ready = asyncio.Event()
        self.sensors = []

    async def async_refresh(self, now=None):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            api_response = await self.api.get_data()
            self.ready.set()
        except InverterError as err:
            if now is not None:
                self.ready.clear()
                return
            raise PlatformNotReady from err
        data = api_response.data
        for sensor in self.sensors:
            if sensor.key in data:
                sensor.value = data[sensor.key]
                sensor.async_schedule_update_ha_state()


class Inverter(SensorEntity):
    """Class for a sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        uid,
        serial,
        version,
        key,
        unit,
        state_class=None,
        device_class=None,
    ):
        """Initialize an inverter sensor."""
        self._attr_unique_id = uid
        self._attr_name = f"Solax {serial} {key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer=MANUFACTURER,
            name=f"Solax {serial}",
            sw_version=version,
        )
        self.key = key
        self.value = None

    @property
    def native_value(self):
        """State of this inverter attribute."""
        return self.value
