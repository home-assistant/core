#!/usr/bin/env python3
"""Support for Tuya switches."""

import logging
from typing import List, Optional

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.sensor import DOMAIN as DEVICE_DOMAIN, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .base import TuyaHaDevice
from .const import (
    DOMAIN,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_TUYA_MAP,
)

_LOGGER = logging.getLogger(__name__)

TUYA_SUPPORT_TYPE = [
    "wsdcg",  # Temperature and Humidity Sensor
    "mcs",  # Door Window Sensor
    "ywbj",  # Somke Detector
    "rqbj",  # Gas Detector
    "pir",  # PIR Detector
    "sj",  # Water Detector
    "pm2.5",  # PM2.5 Sensor
]

# Smoke Detector
# https://developer.tuya.com/en/docs/iot/s?id=K9gf48r5i2iiy
DPCODE_BATTERY = "va_battery"
DPCODE_BATTERY_PERCENTAGE = "battery_percentage"
DPCODE_BATTERY_CODE = "battery"

DPCODE_TEMPERATURE = "va_temperature"
DPCODE_HUMIDITY = "va_humidity"

DPCODE_PM100_VALUE = "pm100_value"
DPCODE_PM25_VALUE = "pm25_value"
DPCODE_PM10_VALUE = "pm10_value"

DPCODE_TEMP_CURRENT = "temp_current"
DPCODE_HUMIDITY_VALUE = "humidity_value"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up tuya sensors dynamically through tuya discovery."""
    print("sensor init")

    hass.data[DOMAIN][TUYA_HA_TUYA_MAP].update({DEVICE_DOMAIN: TUYA_SUPPORT_TYPE})

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya sensor."""
        print("sensor add->", dev_ids)
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(_setup_entities, hass, dev_ids)
        hass.data[DOMAIN][TUYA_HA_DEVICES].extend(entities)
        async_add_entities(entities)

    async_dispatcher_connect(
        hass, TUYA_DISCOVERY_NEW.format(DEVICE_DOMAIN), async_discover_device
    )

    device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
    device_ids = []
    for (device_id, device) in device_manager.deviceMap.items():
        if device.category in TUYA_SUPPORT_TYPE:
            device_ids.append(device_id)
    await async_discover_device(device_ids)


def _setup_entities(hass, device_ids: List):
    """Set up Tuya Switch device."""
    device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
    entities = []
    for device_id in device_ids:
        device = device_manager.deviceMap[device_id]
        if device is None:
            continue

        if DPCODE_BATTERY in device.status:
            entities.append(
                TuyaHaSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_BATTERY,
                    DPCODE_BATTERY,
                    PERCENTAGE,
                )
            )
        if DPCODE_BATTERY_PERCENTAGE in device.status:
            entities.append(
                TuyaHaSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_BATTERY,
                    DPCODE_BATTERY_PERCENTAGE,
                    PERCENTAGE,
                )
            )
        if DPCODE_BATTERY_CODE in device.status:
            entities.append(
                TuyaHaSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_BATTERY,
                    DPCODE_BATTERY_CODE,
                    PERCENTAGE,
                )
            )

        if DPCODE_TEMPERATURE in device.status:
            entities.append(
                TuyaHaSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_TEMPERATURE,
                    DPCODE_TEMPERATURE,
                    TEMP_CELSIUS,
                )
            )
        if DPCODE_TEMP_CURRENT in device.status:
            entities.append(
                TuyaHaSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_TEMPERATURE,
                    DPCODE_TEMP_CURRENT,
                    TEMP_CELSIUS,
                )
            )

        if DPCODE_HUMIDITY in device.status:
            entities.append(
                TuyaHaSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_HUMIDITY,
                    DPCODE_HUMIDITY,
                    PERCENTAGE,
                )
            )
        if DPCODE_HUMIDITY_VALUE in device.status:
            entities.append(
                TuyaHaSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_HUMIDITY,
                    DPCODE_HUMIDITY_VALUE,
                    PERCENTAGE,
                )
            )

        if DPCODE_PM100_VALUE in device.status:
            entities.append(
                TuyaHaSensor(
                    device, device_manager, "PM10", DPCODE_PM100_VALUE, "ug/m³"
                )
            )
        if DPCODE_PM25_VALUE in device.status:
            entities.append(
                TuyaHaSensor(
                    device, device_manager, "PM2.5", DPCODE_PM25_VALUE, "ug/m³"
                )
            )
        if DPCODE_PM10_VALUE in device.status:
            entities.append(
                TuyaHaSensor(
                    device, device_manager, "PM1.0", DPCODE_PM10_VALUE, "ug/m³"
                )
            )

    return entities


class TuyaHaSensor(TuyaHaDevice, SensorEntity):
    """Tuya Sensor Device."""

    def __init__(
        self,
        device: TuyaDevice,
        deviceManager: TuyaDeviceManager,
        sensor_type: str,
        sensor_code: str,
        sensor_unit: str,
    ):
        """Init TuyaHaSensor."""
        self._type = sensor_type
        self._code = sensor_code
        self._unit = sensor_unit
        super().__init__(device, deviceManager)

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{super().unique_id}{self._code}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.tuya_device.name + "_" + self._type

    @property
    def state(self):
        """Return the state of the sensor."""
        return str(self.tuya_device.status.get(self._code))

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._type

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return True
