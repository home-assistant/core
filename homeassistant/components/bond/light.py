"""Support for Bond lights."""
from __future__ import annotations

import logging
from typing import Any

from bond_api import Action, BPUPSubscriptions, DeviceType

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BondHub
from .const import BPUP_SUBS, DOMAIN, HUB
from .entity import BondEntity
from .utils import BondDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bond light devices."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: BondHub = data[HUB]
    bpup_subs: BPUPSubscriptions = data[BPUP_SUBS]

    fan_lights: list[Entity] = [
        BondLight(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_fan(device.type)
        and device.supports_light()
        and not (device.supports_up_light() and device.supports_down_light())
    ]

    fan_up_lights: list[Entity] = [
        BondUpLight(hub, device, bpup_subs, "up_light")
        for device in hub.devices
        if DeviceType.is_fan(device.type) and device.supports_up_light()
    ]

    fan_down_lights: list[Entity] = [
        BondDownLight(hub, device, bpup_subs, "down_light")
        for device in hub.devices
        if DeviceType.is_fan(device.type) and device.supports_down_light()
    ]

    fireplaces: list[Entity] = [
        BondFireplace(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_fireplace(device.type)
    ]

    fp_lights: list[Entity] = [
        BondLight(hub, device, bpup_subs, "light")
        for device in hub.devices
        if DeviceType.is_fireplace(device.type) and device.supports_light()
    ]

    lights: list[Entity] = [
        BondLight(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_light(device.type)
    ]

    async_add_entities(
        fan_lights + fan_up_lights + fan_down_lights + fireplaces + fp_lights + lights,
        True,
    )


class BondBaseLight(BondEntity, LightEntity):
    """Representation of a Bond light."""

    _attr_supported_features = 0


class BondLight(BondBaseLight, BondEntity, LightEntity):
    """Representation of a Bond light."""

    def __init__(
        self,
        hub: BondHub,
        device: BondDevice,
        bpup_subs: BPUPSubscriptions,
        sub_device: str | None = None,
    ) -> None:
        """Create HA entity representing Bond light."""
        super().__init__(hub, device, bpup_subs, sub_device)
        if device.supports_set_brightness():
            self._attr_supported_features = SUPPORT_BRIGHTNESS

    def _apply_state(self, state: dict) -> None:
        self._attr_is_on = state.get("light") == 1
        brightness = state.get("brightness")
        self._attr_brightness = round(brightness * 255 / 100) if brightness else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness:
            await self._hub.bond.action(
                self._device.device_id,
                Action.set_brightness(round((brightness * 100) / 255)),
            )
        else:
            await self._hub.bond.action(self._device.device_id, Action.turn_light_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._hub.bond.action(self._device.device_id, Action.turn_light_off())


class BondDownLight(BondBaseLight, BondEntity, LightEntity):
    """Representation of a Bond light."""

    def _apply_state(self, state: dict) -> None:
        self._attr_is_on = bool(state.get("down_light") and state.get("light"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._hub.bond.action(
            self._device.device_id, Action(Action.TURN_DOWN_LIGHT_ON)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._hub.bond.action(
            self._device.device_id, Action(Action.TURN_DOWN_LIGHT_OFF)
        )


class BondUpLight(BondBaseLight, BondEntity, LightEntity):
    """Representation of a Bond light."""

    def _apply_state(self, state: dict) -> None:
        self._attr_is_on = bool(state.get("up_light") and state.get("light"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._hub.bond.action(
            self._device.device_id, Action(Action.TURN_UP_LIGHT_ON)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._hub.bond.action(
            self._device.device_id, Action(Action.TURN_UP_LIGHT_OFF)
        )


class BondFireplace(BondEntity, LightEntity):
    """Representation of a Bond-controlled fireplace."""

    _attr_supported_features = SUPPORT_BRIGHTNESS

    def _apply_state(self, state: dict) -> None:
        power = state.get("power")
        flame = state.get("flame")
        self._attr_is_on = power == 1
        self._attr_brightness = round(flame * 255 / 100) if flame else None
        self._attr_icon = "mdi:fireplace" if power == 1 else "mdi:fireplace-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fireplace on."""
        _LOGGER.debug("Fireplace async_turn_on called with: %s", kwargs)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness:
            flame = round((brightness * 100) / 255)
            await self._hub.bond.action(self._device.device_id, Action.set_flame(flame))
        else:
            await self._hub.bond.action(self._device.device_id, Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fireplace off."""
        _LOGGER.debug("Fireplace async_turn_off called with: %s", kwargs)

        await self._hub.bond.action(self._device.device_id, Action.turn_off())
