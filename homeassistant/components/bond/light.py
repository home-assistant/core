"""Support for Bond lights."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp.client_exceptions import ClientResponseError
from bond_async import Action, DeviceType

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BondConfigEntry
from .entity import BondEntity
from .models import BondData
from .utils import BondDevice, BondGroup

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BondConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Bond light devices."""
    data = entry.runtime_data
    hub = data.hub

    devices = hub.devices + hub.groups

    fan_lights: list[Entity] = [
        BondLight(data, device)
        for device in devices
        if DeviceType.is_fan(device.type)
        and device.supports_light()
        and not (device.supports_up_light() and device.supports_down_light())
    ]

    fan_up_lights: list[Entity] = [
        BondUpLight(data, device, "up_light")
        for device in devices
        if DeviceType.is_fan(device.type) and device.supports_up_light()
    ]

    fan_down_lights: list[Entity] = [
        BondDownLight(data, device, "down_light")
        for device in devices
        if DeviceType.is_fan(device.type) and device.supports_down_light()
    ]

    fireplaces: list[Entity] = [
        BondFireplace(data, device)
        for device in devices
        if DeviceType.is_fireplace(device.type)
    ]

    fp_lights: list[Entity] = [
        BondLight(data, device, "light")
        for device in devices
        if DeviceType.is_fireplace(device.type) and device.supports_light()
    ]

    lights: list[Entity] = [
        BondLight(data, device)
        for device in devices
        if DeviceType.is_light(device.type)
    ]

    async_add_entities(
        fan_lights + fan_up_lights + fan_down_lights + fireplaces + fp_lights + lights,
    )


class BondBaseLight(BondEntity, LightEntity):
    """Representation of a Bond light."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    async def async_set_brightness_belief(self, brightness: int) -> None:
        """Set the belief state of the light."""
        self._async_ensure_device_only(Action.SET_STATE_BELIEF)
        if not self._device.supports_set_brightness():
            raise HomeAssistantError("This device does not support setting brightness")
        if brightness == 0:
            await self.async_set_power_belief(False)
            return
        try:
            await self._async_action(
                Action.set_brightness_belief(round((brightness * 100) / 255))
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_brightness_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set the belief state of the light."""
        self._async_ensure_device_only(Action.SET_STATE_BELIEF)
        try:
            await self._async_action(Action.set_light_state_belief(power_state))
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_light_state_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex


class BondLight(BondBaseLight):
    """Representation of a Bond light."""

    def __init__(
        self,
        data: BondData,
        device: BondDevice | BondGroup,
        sub_device: str | None = None,
    ) -> None:
        """Create HA entity representing Bond light."""
        super().__init__(data, device, sub_device)
        if device.supports_set_brightness():
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def _apply_state(self) -> None:
        state = self._device.state
        light = state.get("light")
        if isinstance(self._device, BondGroup):
            self._attr_is_on = None if light is None else light == 1
        else:
            self._attr_is_on = light == 1
        brightness = state.get("brightness")
        self._attr_brightness = round(brightness * 255 / 100) if brightness else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if brightness := kwargs.get(ATTR_BRIGHTNESS):
            await self._async_action(
                Action.set_brightness(round((brightness * 100) / 255))
            )
        else:
            await self._async_action(Action.turn_light_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_action(Action.turn_light_off())

    @callback
    def _async_has_action_or_raise(self, action: str) -> None:
        """Raise HomeAssistantError if the device does not support an action."""
        if not self._device.has_action(action):
            raise HomeAssistantError(f"{self.entity_id} does not support {action}")

    async def async_start_increasing_brightness(self) -> None:
        """Start increasing the light brightness."""
        _LOGGER.warning(
            "The bond.start_increasing_brightness service is deprecated and has been"
            " replaced with a button; Call the button.press service instead"
        )
        self._async_has_action_or_raise(Action.START_INCREASING_BRIGHTNESS)
        await self._async_action(Action(Action.START_INCREASING_BRIGHTNESS))

    async def async_start_decreasing_brightness(self) -> None:
        """Start decreasing the light brightness."""
        _LOGGER.warning(
            "The bond.start_decreasing_brightness service is deprecated and has been"
            " replaced with a button; Call the button.press service instead"
        )
        self._async_has_action_or_raise(Action.START_DECREASING_BRIGHTNESS)
        await self._async_action(Action(Action.START_DECREASING_BRIGHTNESS))

    async def async_stop(self) -> None:
        """Stop all actions and clear the queue."""
        _LOGGER.warning(
            "The bond.stop service is deprecated and has been replaced with a button;"
            " Call the button.press service instead"
        )
        self._async_has_action_or_raise(Action.STOP)
        await self._async_action(Action(Action.STOP))


class BondDownLight(BondBaseLight):
    """Representation of a Bond light."""

    def _apply_state(self) -> None:
        state = self._device.state
        down_light = state.get("down_light")
        light = state.get("light")
        if isinstance(self._device, BondGroup):
            self._attr_is_on = (
                None
                if down_light is None or light is None
                else bool(down_light and light)
            )
        else:
            self._attr_is_on = bool(down_light and light)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_action(Action(Action.TURN_DOWN_LIGHT_ON))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_action(Action(Action.TURN_DOWN_LIGHT_OFF))


class BondUpLight(BondBaseLight):
    """Representation of a Bond light."""

    def _apply_state(self) -> None:
        state = self._device.state
        up_light = state.get("up_light")
        light = state.get("light")
        if isinstance(self._device, BondGroup):
            self._attr_is_on = (
                None if up_light is None or light is None else bool(up_light and light)
            )
        else:
            self._attr_is_on = bool(up_light and light)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_action(Action(Action.TURN_UP_LIGHT_ON))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_action(Action(Action.TURN_UP_LIGHT_OFF))


class BondFireplace(BondEntity, LightEntity):
    """Representation of a Bond-controlled fireplace."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_translation_key = "fireplace"

    def _apply_state(self) -> None:
        state = self._device.state
        power = state.get("power")
        flame = state.get("flame")
        self._attr_is_on = power == 1
        self._attr_brightness = round(flame * 255 / 100) if flame else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fireplace on."""
        _LOGGER.debug("Fireplace async_turn_on called with: %s", kwargs)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            flame = round((brightness * 100) / 255)
            await self._async_action(Action.set_flame(flame))
            return

        await self._async_action(Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fireplace off."""
        _LOGGER.debug("Fireplace async_turn_off called with: %s", kwargs)

        await self._async_action(Action.turn_off())

    async def async_set_brightness_belief(self, brightness: int) -> None:
        """Set the belief state of the light."""
        self._async_ensure_device_only(Action.SET_STATE_BELIEF)
        if not self._device.supports_set_brightness():
            raise HomeAssistantError("This device does not support setting brightness")
        if brightness == 0:
            await self.async_set_power_belief(False)
            return
        try:
            await self._async_action(
                Action.set_brightness_belief(round((brightness * 100) / 255))
            )
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_brightness_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex

    async def async_set_power_belief(self, power_state: bool) -> None:
        """Set the belief state of the light."""
        self._async_ensure_device_only(Action.SET_STATE_BELIEF)
        try:
            await self._async_action(Action.set_power_state_belief(power_state))
        except ClientResponseError as ex:
            raise HomeAssistantError(
                "The bond API returned an error calling set_power_state_belief for"
                f" {self.entity_id}.  Code: {ex.status}  Message: {ex.message}"
            ) from ex
