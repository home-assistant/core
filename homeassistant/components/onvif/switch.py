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
from .models import Profile


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a ONVIF switch platform."""
    device = hass.data[DOMAIN][config_entry.unique_id]

    entities = []
    for profile in device.profiles:
        entities.extend(
            [
                ONVIFWiperSwitch("_wiper", profile, device),
                ONVIFAutoFocusSwitch("_autofocus", profile, device),
            ]
        )
        # only add controls for the first media profile, since controlling
        # settings for other resolutions would be redundant
        break
    async_add_entities(entities)


class ONVIFImagingSettingSwitch(ONVIFBaseEntity, SwitchEntity):
    """An ONVIF switch controlled via ImagingSettings."""

    _on_settings: dict[str, Any] = {}
    _off_settings: dict[str, Any] = {}

    def __init__(self, uid: str, profile: Profile, device: ONVIFDevice) -> None:
        """Initialize the switch."""
        self._profile = profile
        super().__init__(device)
        unique_root = "_".join([str(self.device_info["name"]), profile.name])
        self._attr_unique_id = unique_root + uid

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        self._attr_is_on = True
        await self.device.async_set_imaging_settings(self._profile, self._on_settings)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        self._attr_is_on = False
        await self.device.async_set_imaging_settings(self._profile, self._off_settings)


class ONVIFAuxSwitch(ONVIFBaseEntity, SwitchEntity):
    """An ONVIF switch controlled via ONVIF Auxiliary Commands."""

    _on_cmd = ""
    _off_cmd = ""

    def __init__(self, uid: str, profile: Profile, device: ONVIFDevice) -> None:
        """Initialize the switch."""
        self._profile = profile
        super().__init__(device)
        unique_root = "_".join([str(self.device_info["name"]), profile.name])
        self._attr_unique_id = unique_root + uid

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on switch."""
        self._attr_is_on = True
        await self.device.async_run_aux_command(self._profile, self._on_cmd)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off switch."""
        self._attr_is_on = True
        await self.device.async_run_aux_command(self._profile, self._off_cmd)


class ONVIFAutoFocusSwitch(ONVIFImagingSettingSwitch):
    """Turn auto-focus on or off."""

    _on_settings = {"Focus": {"AutoFocusMode": "AUTO"}}
    _off_settings = {"Focus": {"AutoFocusMode": "MANUAL"}}


class ONVIFWiperSwitch(ONVIFAuxSwitch):
    """Turn wiper on or off."""

    _on_cmd = "tt:Wiper|On"
    _off_cmd = "tt:Wiper|Off"
