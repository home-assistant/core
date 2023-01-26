"""ONVIF switches for controlling cameras."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ONVIFBaseEntity
from .const import DOMAIN
from .device import ONVIFDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a ONVIF switch platform."""
    device = hass.data[DOMAIN][config_entry.unique_id]

    entities = [
        ONVIFWiperSwitch(device),
        ONVIFAutoFocusSwitch(device),
        ONVIFInfraredSwitch(device),
    ]
    async_add_entities(entities)


class ONVIFImagingSettingSwitch(ONVIFBaseEntity, SwitchEntity):
    """An ONVIF switch controlled via ImagingSettings."""

    _on_settings: dict[str, Any] = {}
    _off_settings: dict[str, Any] = {}

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        self._attr_is_on = True
        profile = self.device.profiles[0]
        await self.device.async_set_imaging_settings(profile, self._on_settings)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        self._attr_is_on = False
        profile = self.device.profiles[0]
        await self.device.async_set_imaging_settings(profile, self._off_settings)


class ONVIFAuxSwitch(ONVIFBaseEntity, SwitchEntity):
    """An ONVIF switch controlled via ONVIF Auxiliary Commands."""

    _on_cmd = ""
    _off_cmd = ""

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        self._attr_is_on = True
        profile = self.device.profiles[0]
        await self.device.async_run_aux_command(profile, self._on_cmd)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        self._attr_is_on = False
        profile = self.device.profiles[0]
        await self.device.async_run_aux_command(profile, self._off_cmd)


class ONVIFAutoFocusSwitch(ONVIFImagingSettingSwitch):
    """Turn auto-focus on or off."""

    _on_settings = {"Focus": {"AutoFocusMode": "AUTO"}}
    _off_settings = {"Focus": {"AutoFocusMode": "MANUAL"}}

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the switch."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} Autofocus"
        self._attr_unique_id = f"{self.mac_or_serial}_autofocus"


class ONVIFInfraredSwitch(ONVIFImagingSettingSwitch):
    """Turn IR lamp on or off."""

    # turning cut filter off forces the IR lamp on
    # note that there may also an auto setting
    _on_settings = {"IrCutFilter": "OFF"}
    _off_settings = {"IrCutFilter": "ON"}

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the switch."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} IR Lamp"
        self._attr_unique_id = f"{self.mac_or_serial}_ir_lamp"


class ONVIFWiperSwitch(ONVIFAuxSwitch):
    """Turn wiper on or off."""

    _on_cmd = "tt:Wiper|On"
    _off_cmd = "tt:Wiper|Off"

    def __init__(self, device: ONVIFDevice) -> None:
        """Initialize the switch."""
        super().__init__(device)
        self._attr_name = f"{self.device.name} Wiper"
        self._attr_unique_id = f"{self.mac_or_serial}_wiper"
