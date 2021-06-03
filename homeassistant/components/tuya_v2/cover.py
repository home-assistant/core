#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Support for Tuya Cover."""

import logging
import json
from typing import Any, Dict, List, Optional, Tuple, cast

from homeassistant.core import HomeAssistant, Config
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.cover import (
    CoverEntity,
    DEVICE_CLASS_CURTAIN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    SUPPORT_OPEN,
    SUPPORT_CLOSE,
    DOMAIN as DEVICE_DOMAIN
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect
)

from .const import (
    DOMAIN,
    TUYA_HA_TUYA_MAP,
    TUYA_DISCOVERY_NEW,
    TUYA_DEVICE_MANAGER
)

from .base import TuyaHaDevice

_LOGGER = logging.getLogger(__name__)

TUYA_SUPPORT_TYPE = {
    "cl",  # Curtain
    "clkg" # Curtain Switch
}

# Curtain
# https://developer.tuya.com/en/docs/iot/f?id=K9gf46o5mtfyc
DPCODE_CONTROL = 'control'
DPCODE_PERCENT_CONTROL = 'percent_control'

ATTR_POSITION = 'position'


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up tuya cover dynamically through tuya discovery."""
    print("cover init")

    hass.data[DOMAIN][TUYA_HA_TUYA_MAP].update({DEVICE_DOMAIN: TUYA_SUPPORT_TYPE})

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya cover."""
        print("cover add->", dev_ids)
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(
            _setup_entities,
            hass,
            dev_ids
        )
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
    """Set up Tuya Cover."""
    device_manager = hass.data[DOMAIN][TUYA_DEVICE_MANAGER]
    entities = []
    for device_id in device_ids:
        device = device_manager.deviceMap[device_id]
        if device is None:
            continue
        entities.append(TuyaHaCover(device, device_manager))
    return entities

class TuyaHaCover(TuyaHaDevice, CoverEntity):
    """Tuya Switch Device."""

    platform = 'cover'

    # property
    @property
    def device_class(self) -> str:
        """Return Entity Properties."""
        return DEVICE_CLASS_CURTAIN
    
    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed or not."""
        return None
    
    @property
    def current_cover_position(self) -> int:
        return self.tuyaDevice.status.get(DPCODE_PERCENT_CONTROL, 0) 

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.tuyaDeviceManager.sendCommands(
            self.tuyaDevice.id, [{'code': DPCODE_CONTROL, 'value': 'open'}])

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self.tuyaDeviceManager.sendCommands(
            self.tuyaDevice.id, [{'code': DPCODE_CONTROL, 'value': 'close'}])

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self.tuyaDeviceManager.sendCommands(
            self.tuyaDevice.id, [{'code': DPCODE_CONTROL, 'value': 'stop'}])
    
    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        print("cover-->", kwargs)
        self.tuyaDeviceManager.sendCommands(
            self.tuyaDevice.id, [{'code': DPCODE_PERCENT_CONTROL, 'value': kwargs[ATTR_POSITION]}])
    
    @property
    def supported_features(self):
        """Flag supported features."""
        supports = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

        if DPCODE_PERCENT_CONTROL in self.tuyaDevice.status:
            supports = supports | SUPPORT_SET_POSITION
        
        return supports

    
