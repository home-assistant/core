"""Light platform for UniFi Network integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.devices import Devices
from aiounifi.models.api import ApiItem
from aiounifi.models.device import Device, DeviceSetLedStatus

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import rgb_hex_to_rgb_list

from . import UnifiConfigEntry
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_device_available_fn,
    async_device_device_info_fn,
)

if TYPE_CHECKING:
    from .hub import UnifiHub


@callback
def async_device_led_supported_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if device supports LED control."""
    device: Device = hub.api.devices[obj_id]
    return device.supports_led_ring


@callback
def async_device_led_is_on_fn(hub: UnifiHub, device: Device) -> bool:
    """Check if device LED is on."""
    return device.led_override == "on"


async def async_device_led_control_fn(
    hub: UnifiHub, obj_id: str, turn_on: bool, **kwargs: Any
) -> None:
    """Control device LED."""
    device = hub.api.devices[obj_id]

    status = "on" if turn_on else "off"

    brightness = (
        int((kwargs[ATTR_BRIGHTNESS] / 255) * 100)
        if ATTR_BRIGHTNESS in kwargs
        else device.led_override_color_brightness
    )

    color = (
        f"#{kwargs[ATTR_RGB_COLOR][0]:02x}{kwargs[ATTR_RGB_COLOR][1]:02x}{kwargs[ATTR_RGB_COLOR][2]:02x}"
        if ATTR_RGB_COLOR in kwargs
        else device.led_override_color
    )

    await hub.api.request(
        DeviceSetLedStatus.create(
            device=device,
            status=status,
            brightness=brightness,
            color=color,
        )
    )


@dataclass(frozen=True, kw_only=True)
class UnifiLightEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    LightEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi light entity."""

    control_fn: Callable[[UnifiHub, str, bool], Coroutine[Any, Any, None]]
    is_on_fn: Callable[[UnifiHub, ApiItemT], bool]


ENTITY_DESCRIPTIONS: tuple[UnifiLightEntityDescription, ...] = (
    UnifiLightEntityDescription[Devices, Device](
        key="LED control",
        translation_key="led_control",
        allowed_fn=lambda hub, obj_id: True,
        api_handler_fn=lambda api: api.devices,
        available_fn=async_device_available_fn,
        control_fn=async_device_led_control_fn,
        device_info_fn=async_device_device_info_fn,
        is_on_fn=async_device_led_is_on_fn,
        name_fn=lambda device: "LED",
        object_fn=lambda api, obj_id: api.devices[obj_id],
        supported_fn=async_device_led_supported_fn,
        unique_id_fn=lambda hub, obj_id: f"led-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities,
        UnifiLightEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiLightEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], LightEntity
):
    """Base representation of a UniFi light."""

    entity_description: UnifiLightEntityDescription[HandlerT, ApiItemT]
    _attr_supported_features = LightEntityFeature(0)
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state."""
        self.async_update_state(ItemEvent.ADDED, self._obj_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        await self.entity_description.control_fn(self.hub, self._obj_id, True, **kwargs)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        await self.entity_description.control_fn(
            self.hub, self._obj_id, False, **kwargs
        )

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state."""
        description = self.entity_description
        device_obj = description.object_fn(self.api, self._obj_id)

        device = cast(Device, device_obj)

        self._attr_is_on = description.is_on_fn(self.hub, device_obj)

        brightness = device.led_override_color_brightness
        self._attr_brightness = (
            int((int(brightness) / 100) * 255) if brightness is not None else None
        )

        hex_color = (
            device.led_override_color.lstrip("#")
            if self._attr_is_on and device.led_override_color
            else None
        )
        if hex_color and len(hex_color) == 6:
            rgb_list = rgb_hex_to_rgb_list(hex_color)
            self._attr_rgb_color = (rgb_list[0], rgb_list[1], rgb_list[2])
        else:
            self._attr_rgb_color = None
