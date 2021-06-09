#!/usr/bin/env python3
"""Support for Tuya Humidifiers."""

import json
import logging
from typing import List

from homeassistant.components.humidifier import (
    DOMAIN as DEVICE_DOMAIN,
    SUPPORT_MODES,
    HumidifierEntity,
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

TUYA_SUPPORT_TYPE = {
    "jsq",  # Humidifier
}

# Humidifier(jsq)
# https://developers.home-assistant.io/docs/core/entity/humidifier
DPCODE_MODE = "mode"
DPCODE_SWITCH = "switch"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up tuya sensors dynamically through tuya discovery."""
    print("humidifier init")

    hass.data[DOMAIN][TUYA_HA_TUYA_MAP].update({DEVICE_DOMAIN: TUYA_SUPPORT_TYPE})

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya sensor."""
        print("humidifier add->", dev_ids)
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

        entities.append(TuyaHaHumidifier(device, device_manager))

    return entities


class TuyaHaHumidifier(TuyaHaDevice, HumidifierEntity):
    """Tuya Switch Device."""

    @property
    def is_on(self):
        """Return the device is on or off."""
        return self.tuya_device.status.get(DPCODE_SWITCH, False)

    @property
    def mode(self):
        """Return the current mode."""
        return self.tuya_device.status.get(DPCODE_MODE)

    @property
    def available_modes(self):
        """Return a list of available modes."""
        return json.loads(self.tuya_device.function.get(DPCODE_MODE, {}).values).get(
            "range"
        )

    @property
    def supported_features(self):
        """Return humidifier support features."""
        supports = 0
        if DPCODE_MODE in self.tuya_device.status:
            supports = supports | SUPPORT_MODES
        return supports

    def set_mode(self, mode):
        """Set new target preset mode."""
        self.tuya_device_manager.sendCommands(
            self.tuya_device.id, [{"code": DPCODE_MODE, "value": mode}]
        )

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.tuya_device_manager.sendCommands(
            self.tuya_device.id, [{"code": DPCODE_SWITCH, "value": True}]
        )

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.tuya_device_manager.sendCommands(
            self.tuya_device.id, [{"code": DPCODE_SWITCH, "value": False}]
        )
