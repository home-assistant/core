#!/usr/bin/env python3
"""Support for Tuya Binary Sensor."""

import logging
from typing import Callable, List, Optional

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SMOKE,
    DOMAIN as DEVICE_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
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
    "mcs",  # Door Window Sensor
    "ywbj",  # Smoke Detector
    "rqbj",  # Gas Detector
    "pir",  # PIR Detector
    "sj",  # Water Detector
    "sos",  # Emergency Button
    "hps",  # Human Presence Sensor
]

# Door Window Sensor
# https://developer.tuya.com/en/docs/iot/s?id=K9gf48hm02l8m

DPCODE_SWITCH = "switch"

DPCODE_SMOKE_SENSOR_STATE = "smoke_sensor_state"
DPCODE_GAS_SENSOR_STATE = "gas_sensor_state"
DPCODE_PIR = "pir"
DPCODE_WATER_SENSOR_STATE = "watersensor_state"
DPCODE_SOS_STATE = "sos_state"
DPCODE_PRESENCE_STATE = "presence_state"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up tuya binary sensors dynamically through tuya discovery."""
    print("binary sensor init")

    hass.data[DOMAIN][TUYA_HA_TUYA_MAP].update({DEVICE_DOMAIN: TUYA_SUPPORT_TYPE})

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya sensor."""
        print("binary sensor add->", dev_ids)
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

        if DPCODE_SWITCH in device.status:
            entities.append(
                TuyaHaBSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_DOOR,
                    (lambda d: d.status.get(DPCODE_SWITCH, False)),
                )
            )
        if DPCODE_SMOKE_SENSOR_STATE in device.status:
            entities.append(
                TuyaHaBSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_SMOKE,
                    (lambda d: "1" == d.status.get(DPCODE_SMOKE_SENSOR_STATE, 1)),
                )
            )
        if DPCODE_GAS_SENSOR_STATE in device.status:
            entities.append(
                TuyaHaBSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_GAS,
                    (lambda d: "1" == d.status.get(DPCODE_GAS_SENSOR_STATE, 1)),
                )
            )
        if DPCODE_PIR in device.status:
            entities.append(
                TuyaHaBSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_MOTION,
                    (lambda d: "pir" == d.status.get(DPCODE_PIR, "none")),
                )
            )
        if DPCODE_WATER_SENSOR_STATE in device.status:
            entities.append(
                TuyaHaBSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_MOISTURE,
                    (lambda d: "1" == d.status.get(DPCODE_WATER_SENSOR_STATE, "none")),
                )
            )
        if DPCODE_SOS_STATE in device.status:
            entities.append(
                TuyaHaBSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_PROBLEM,
                    (lambda d: d.status.get(DPCODE_SOS_STATE, False)),
                )
            )
        if DPCODE_PRESENCE_STATE in device.status:
            entities.append(
                TuyaHaBSensor(
                    device,
                    device_manager,
                    DEVICE_CLASS_MOTION,
                    (
                        lambda d: "presence"
                        == d.status.get(DPCODE_PRESENCE_STATE, "none")
                    ),
                )
            )

    return entities


class TuyaHaBSensor(TuyaHaDevice, BinarySensorEntity):
    """Tuya Binary Sensor Device."""

    def __init__(
        self,
        device: TuyaDevice,
        deviceManager: TuyaDeviceManager,
        sensor_type: str,
        sensor_is_on: Callable[..., bool],
    ):
        """Init TuyaHaBSensor."""
        self._type = sensor_type
        self._is_on = sensor_is_on
        super().__init__(device, deviceManager)

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{super().unique_id}{self._type}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.tuya_device.name + "_" + self._type

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on(self.tuya_device)

    @property
    def device_class(self):
        """Device class of this entity."""
        return self._type

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return True
