#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Support for Tuya switches."""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from tuya_iot import TuyaDeviceManager, TuyaDevice, device

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    DOMAIN as DEVICE_DOMAIN,
    SUPPORT_ALARM_TRIGGER,
)
from homeassistant.const import (
    STATE_ALARM_DISARMED,
    STATE_ALARM_ARMING,
    STATE_ALARM_TRIGGERED
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect
)

from .const import (
    DOMAIN,
    TUYA_HA_TUYA_MAP,
    TUYA_DISCOVERY_NEW,
    TUYA_DEVICE_MANAGER,
    TUYA_HA_DEVICES
)

from .base import TuyaHaDevice

_LOGGER = logging.getLogger(__name__)

TUYA_SUPPORT_TYPE = [
    "ywbj",   # Somke Detector
    'rqbj',   # Gas Detector
    "pir"     # PIR Detector
]

# Smoke Detector 
# https://developer.tuya.com/en/docs/iot/s?id=K9gf48r5i2iiy

DPCODE_SMOKE_SENSOR_STATE = 'smoke_sensor_state'
DPCODE_GAS_SENSOR_STATE = 'gas_sensor_state'
DPCODE_PIR = 'pir'


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up tuya alarm dynamically through tuya discovery."""
    print("alarm init")

    hass.data[DOMAIN][TUYA_HA_TUYA_MAP].update({DEVICE_DOMAIN: TUYA_SUPPORT_TYPE})

    # platform = config_entry.data[CONF_PLATFORM]

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya sensor."""
        print("alarm add->", dev_ids)
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(
            _setup_entities,
            hass,
            dev_ids
        )
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

        if DPCODE_SMOKE_SENSOR_STATE in device.status:
            entities.append(TuyaHaAlarm(device, device_manager, (lambda d: STATE_ALARM_TRIGGERED if '1' == d.status.get(DPCODE_SMOKE_SENSOR_STATE, 1) else STATE_ALARM_ARMING)))
        if DPCODE_GAS_SENSOR_STATE in device.status:
            entities.append(TuyaHaAlarm(device, device_manager, (lambda d: STATE_ALARM_TRIGGERED if '1' == d.status.get(DPCODE_GAS_SENSOR_STATE, 1) else STATE_ALARM_ARMING)))
        if DPCODE_PIR in device.stastus:
            entities.append(TuyaHaAlarm(device, device_manager, (lambda d: STATE_ALARM_TRIGGERED if 'pir' == d.status.get(DPCODE_GAS_SENSOR_STATE, 'none') else STATE_ALARM_ARMING)))
        
    return entities


class TuyaHaAlarm(TuyaHaDevice, AlarmControlPanelEntity):
    """Tuya Alarm Device."""

    platform = 'alarm'

    def __init__(self,
                 device: TuyaDevice,
                 deviceManager: TuyaDeviceManager,
                 sensor_is_on: Callable[..., str]):
        super().__init__(device, deviceManager)
        self._is_on = sensor_is_on
    
    @property
    def state(self):
        return self._is_on(self.tuyaDevice)
    
    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_TRIGGER

