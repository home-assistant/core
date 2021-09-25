#!/usr/bin/env python3
"""Support for Tuya switches."""
from __future__ import annotations

import logging
from typing import Any

from tuya_iot import TuyaDevice, TuyaDeviceManager

from homeassistant.components.switch import DOMAIN as DEVICE_DOMAIN, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import TuyaHaEntity
from .const import (
    DOMAIN,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_TUYA_MAP,
)

_LOGGER = logging.getLogger(__name__)

TUYA_SUPPORT_TYPE = {
    "kg",  # Switch
    "cz",  # Socket
    "pc",  # Power Strip
    "bh",  # Smart Kettle
    "dlq",  # Breaker
    "cwysj",  # Pet Water Feeder
    "kj",  # Air Purifier
    "xxj",  # Diffuser
}

# Switch(kg), Socket(cz), Power Strip(pc)
# https://developer.tuya.com/en/docs/iot/categorykgczpc?id=Kaiuz08zj1l4y
DPCODE_SWITCH = "switch"

# Air Purifier
# https://developer.tuya.com/en/docs/iot/categorykj?id=Kaiuz1atqo5l7
# Pet Water Feeder
# https://developer.tuya.com/en/docs/iot/f?id=K9gf46aewxem5
DPCODE_ANION = "anion"  # Air Purifier - Ionizer unit
# Air Purifier - Filter cartridge resetting; Pet Water Feeder - Filter cartridge resetting
DPCODE_FRESET = "filter_reset"
DPCODE_LIGHT = "light"  # Air Purifier - Light
DPCODE_LOCK = "lock"  # Air Purifier - Child lock
# Air Purifier - UV sterilization; Pet Water Feeder - UV sterilization
DPCODE_UV = "uv"
DPCODE_WET = "wet"  # Air Purifier - Humidification unit
DPCODE_PRESET = "pump_reset"  # Pet Water Feeder - Water pump resetting
DPCODE_WRESET = "water_reset"  # Pet Water Feeder - Resetting of water usage days


DPCODE_START = "start"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up tuya sensors dynamically through tuya discovery."""
    _LOGGER.debug("switch init")

    hass.data[DOMAIN][entry.entry_id][TUYA_HA_TUYA_MAP][
        DEVICE_DOMAIN
    ] = TUYA_SUPPORT_TYPE

    async def async_discover_device(dev_ids):
        """Discover and add a discovered tuya sensor."""
        _LOGGER.debug("switch add-> %s", dev_ids)
        if not dev_ids:
            return
        entities = _setup_entities(hass, entry, dev_ids)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, TUYA_DISCOVERY_NEW.format(DEVICE_DOMAIN), async_discover_device
        )
    )

    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    device_ids = []
    for (device_id, device) in device_manager.device_map.items():
        if device.category in TUYA_SUPPORT_TYPE:
            device_ids.append(device_id)
    await async_discover_device(device_ids)


def _setup_entities(hass, entry: ConfigEntry, device_ids: list[str]) -> list[Entity]:
    """Set up Tuya Switch device."""
    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    entities: list[Entity] = []
    for device_id in device_ids:
        device = device_manager.device_map[device_id]
        if device is None:
            continue

        for function in device.function:
            tuya_ha_switch = None
            if device.category == "kj":
                if function in [
                    DPCODE_ANION,
                    DPCODE_FRESET,
                    DPCODE_LIGHT,
                    DPCODE_LOCK,
                    DPCODE_UV,
                    DPCODE_WET,
                ]:
                    tuya_ha_switch = TuyaHaSwitch(device, device_manager, function)
                    # Main device switch is handled by the Fan object
            elif device.category == "cwysj":
                if function in [DPCODE_FRESET, DPCODE_UV, DPCODE_PRESET, DPCODE_WRESET]:
                    tuya_ha_switch = TuyaHaSwitch(device, device_manager, function)

                if function.startswith(DPCODE_SWITCH):
                    # Main device switch
                    tuya_ha_switch = TuyaHaSwitch(device, device_manager, function)
            else:
                if function.startswith(DPCODE_START):
                    tuya_ha_switch = TuyaHaSwitch(device, device_manager, function)
                if function.startswith(DPCODE_SWITCH):
                    tuya_ha_switch = TuyaHaSwitch(device, device_manager, function)

            if tuya_ha_switch is not None:
                entities.append(tuya_ha_switch)
                hass.data[DOMAIN][entry.entry_id][TUYA_HA_DEVICES].add(
                    tuya_ha_switch.tuya_device.id
                )
    return entities


class TuyaHaSwitch(TuyaHaEntity, SwitchEntity):
    """Tuya Switch Device."""

    dp_code_switch = DPCODE_SWITCH
    dp_code_start = DPCODE_START

    def __init__(
        self, device: TuyaDevice, device_manager: TuyaDeviceManager, dp_code: str = ""
    ) -> None:
        """Init TuyaHaSwitch."""
        super().__init__(device, device_manager)

        self.dp_code = dp_code
        self.channel = (
            dp_code.replace(DPCODE_SWITCH, "")
            if dp_code.startswith(DPCODE_SWITCH)
            else dp_code
        )

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{super().unique_id}{self.channel}"

    @property
    def name(self) -> str | None:
        """Return Tuya device name."""
        return f"{self.tuya_device.name}{self.channel}"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.tuya_device.status.get(self.dp_code, False)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        self._send_command([{"code": self.dp_code, "value": True}])

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        self._send_command([{"code": self.dp_code, "value": False}])
