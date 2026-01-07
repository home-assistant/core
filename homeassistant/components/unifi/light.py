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
from homeassistant.const import EntityCategory
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


def convert_brightness_to_unifi(ha_brightness: int) -> int:
    """Convert Home Assistant brightness (0-255) to UniFi brightness (0-100)."""
    return round((ha_brightness / 255) * 100)


def convert_brightness_to_ha(
    unifi_brightness: int,
) -> int:
    """Convert UniFi brightness (0-100) to Home Assistant brightness (0-255)."""
    return round((unifi_brightness / 100) * 255)


def get_device_brightness_or_default(device: Device) -> int:
    """Get device's current LED brightness. Defaults to 100 (full brightness) if not set."""
    value = device.led_override_color_brightness
    return value if value is not None else 100


@callback
def async_device_led_supported_fn(hub: UnifiHub, obj_id: str) -> bool:
    """Check if device supports LED control."""
    device: Device = hub.api.devices[obj_id]
    return device.led_override is not None or device.supports_led_ring


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

    # Only send brightness and RGB if device has LED_RING hardware support
    if device.supports_led_ring:
        # Use provided brightness or fall back to device's current brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = convert_brightness_to_unifi(kwargs[ATTR_BRIGHTNESS])
        else:
            brightness = get_device_brightness_or_default(device)

        # Use provided RGB color or fall back to device's current color
        color: str | None
        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            color = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        else:
            color = device.led_override_color
    else:
        brightness = None
        color = None

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
        entity_category=EntityCategory.CONFIG,
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

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state."""
        device = cast(Device, self.entity_description.object_fn(self.api, self._obj_id))

        if device.supports_led_ring:
            self._attr_supported_color_modes = {ColorMode.RGB}
            self._attr_color_mode = ColorMode.RGB
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

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

        # Only set brightness and RGB if device has LED_RING hardware support
        if device.supports_led_ring:
            self._attr_brightness = convert_brightness_to_ha(
                get_device_brightness_or_default(device)
            )

            # Parse hex color from device and convert to RGB tuple
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
