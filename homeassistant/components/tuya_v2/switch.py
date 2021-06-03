#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Support for Tuya switches."""

import logging
from typing import Any, Dict, List, Optional, Tuple, cast
from tuya_iot import TuyaDeviceManager, TuyaDevice

from homeassistant.core import HomeAssistant, Config
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import (
    SwitchEntity,
    DOMAIN as DEVICE_DOMAIN
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

TUYA_SUPPORT_TYPE = {
    "kg",  # Switch
    "cz",  # Socket
    "pc",  # Power Strip
}

# Switch(kg), Socket(cz), Power Strip(pc)
# https://developer.tuya.com/docs/iot/open-api/standard-function/electrician-category/categorykgczpc?categoryId=486118
DPCODE_SWITCH = 'switch'

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up tuya sensors dynamically through tuya discovery."""
    print("switch init")

    hass.data[DOMAIN][TUYA_HA_TUYA_MAP].update({DEVICE_DOMAIN: TUYA_SUPPORT_TYPE})

    # platform = config_entry.data[CONF_PLATFORM]

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya sensor."""
        print("switch add->", dev_ids)
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
        
        switch_set = []
        for function in device.function:
            if function.startswith(DPCODE_SWITCH):
                switch_set.append(function.replace(DPCODE_SWITCH, ''))
        
        if len(switch_set) > 1:
            for channel in switch_set:
                entities.append(TuyaHaSwitch(device, device_manager, channel))
        elif len(switch_set) == 1:
            entities.append(TuyaHaSwitch(device, device_manager))
        
    return entities

class TuyaHaSwitch(TuyaHaDevice, SwitchEntity):
    """Tuya Switch Device."""

    platform = 'switch'
    dp_code_switch = DPCODE_SWITCH


    def __init__(self, device: TuyaDevice, deviceManager: TuyaDeviceManager, channel:str = ''):
        super().__init__(device, deviceManager)
        
        self.channel = channel
        if len(channel) > 0:
            self.dp_code_switch = DPCODE_SWITCH + self.channel
        else:
            for function in device.function:
                if function.startswith(DPCODE_SWITCH):
                    self.dp_code_switch = function
            
    # ToggleEntity

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self.tuyaDevice.uuid + self.channel

    @property
    def name(self) -> Optional[str]:
        """Return Tuya device name."""
        return self.tuyaDevice.name + self.channel

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.tuyaDevice.status.get(self.dp_code_switch, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self.tuyaDeviceManager.sendCommands(self.tuyaDevice.id, [{'code': self.dp_code_switch, 'value': True}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.tuyaDeviceManager.sendCommands(self.tuyaDevice.id, [{'code': self.dp_code_switch, 'value': False}])
