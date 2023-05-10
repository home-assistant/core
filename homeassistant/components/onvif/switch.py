"""ONVIF switches for controlling cameras."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import ONVIFBaseEntity
from .const import DOMAIN
from .device import ONVIFDevice
from .models import Profile


@dataclass
class ONVIFSwitchEntityDescriptionMixin:
    """Mixin for required keys."""

    turn_on_fn: Callable[
        [ONVIFDevice], Callable[[Profile, Any], Coroutine[Any, Any, None]]
    ]
    turn_off_fn: Callable[
        [ONVIFDevice], Callable[[Profile, Any], Coroutine[Any, Any, None]]
    ]
    turn_on_data: Any
    turn_off_data: Any
    supported_fn: Callable[[ONVIFDevice], bool]


@dataclass
class ONVIFSwitchEntityDescription(
    SwitchEntityDescription, ONVIFSwitchEntityDescriptionMixin
):
    """Describes ONVIF switch entity."""


SWITCHES: tuple[ONVIFSwitchEntityDescription, ...] = (
    ONVIFSwitchEntityDescription(
        key="autofocus",
        name="Autofocus",
        icon="mdi:focus-auto",
        turn_on_data={"Focus": {"AutoFocusMode": "AUTO"}},
        turn_off_data={"Focus": {"AutoFocusMode": "MANUAL"}},
        turn_on_fn=lambda device: device.async_set_imaging_settings,
        turn_off_fn=lambda device: device.async_set_imaging_settings,
        supported_fn=lambda device: device.capabilities.imaging,
    ),
    ONVIFSwitchEntityDescription(
        key="ir_lamp",
        name="IR lamp",
        icon="mdi:spotlight-beam",
        turn_on_data={"IrCutFilter": "OFF"},
        turn_off_data={"IrCutFilter": "ON"},
        turn_on_fn=lambda device: device.async_set_imaging_settings,
        turn_off_fn=lambda device: device.async_set_imaging_settings,
        supported_fn=lambda device: device.capabilities.imaging,
    ),
    ONVIFSwitchEntityDescription(
        key="wiper",
        name="Wiper",
        icon="mdi:wiper",
        turn_on_data="tt:Wiper|On",
        turn_off_data="tt:Wiper|Off",
        turn_on_fn=lambda device: device.async_run_aux_command,
        turn_off_fn=lambda device: device.async_run_aux_command,
        supported_fn=lambda device: device.capabilities.ptz,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a ONVIF switch platform."""
    device = hass.data[DOMAIN][config_entry.unique_id]

    async_add_entities(
        ONVIFSwitch(device, description)
        for description in SWITCHES
        if description.supported_fn(device)
    )


class ONVIFSwitch(ONVIFBaseEntity, SwitchEntity):
    """An ONVIF switch."""

    entity_description: ONVIFSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, device: ONVIFDevice, description: ONVIFSwitchEntityDescription
    ) -> None:
        """Initialize the switch."""
        super().__init__(device)
        self._attr_unique_id = f"{self.mac_or_serial}_{description.key}"
        self.entity_description = description

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        self._attr_is_on = True
        profile = self.device.profiles[0]
        await self.entity_description.turn_on_fn(self.device)(
            profile, self.entity_description.turn_on_data
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        self._attr_is_on = False
        profile = self.device.profiles[0]
        await self.entity_description.turn_off_fn(self.device)(
            profile, self.entity_description.turn_off_data
        )
