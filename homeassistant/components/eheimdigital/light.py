"""EHEIM Digital lights."""

from typing import Any, cast

from eheimdigital.classic_led_ctrl import EheimDigitalClassicLEDControl
from eheimdigital.types import LightMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import EheimDigitalConfigEntry
from .const import DAYCL_MODE, DOMAIN, EFFECT_TO_LIGHT_MODE
from .coordinator import EheimDigitalUpdateCoordinator

BRIGHTNESS_SCALE = (1, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EHEIM Digital lights based on a config entry."""
    coordinator = entry.runtime_data

    registry = er.async_get(hass)
    existing_entities = er.async_entries_for_config_entry(registry, entry.entry_id)

    entities = []

    classic_led_ctrl_devices = [
        device
        for device in coordinator.hub.devices.values()
        if isinstance(device, EheimDigitalClassicLEDControl)
    ]

    for device in classic_led_ctrl_devices:
        for channel in range(2):
            if len(device.tankconfig[channel]) > 0:
                entities.append(
                    EheimDigitalClassicLEDControlLight(coordinator, device, channel)
                )
            else:
                for entity in existing_entities:
                    if entity.unique_id == f"{device.mac_address}_{channel}":
                        registry.async_remove(entity.entity_id)

    async_add_entities(entities)


class EheimDigitalClassicLEDControlLight(
    CoordinatorEntity[EheimDigitalUpdateCoordinator], LightEntity
):
    """Represent a EHEIM Digital classicLEDcontrol light."""

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_effect_list = [DAYCL_MODE]
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: EheimDigitalClassicLEDControl,
        channel: int,
    ) -> None:
        """Initialize an EHEIM Digital classicLEDcontrol light entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            configuration_url="http://eheimdigital.local",
            name=device.name,
            connections={(CONNECTION_NETWORK_MAC, device.mac_address)},
            manufacturer="EHEIM",
            model=device.device_type.model_name,
            identifiers={(DOMAIN, device.mac_address)},
            suggested_area=device.aquarium_name,
            sw_version=device.sw_version,
            via_device=(DOMAIN, coordinator.hub.master.mac_address),
        )
        self._device = device
        self._channel = channel
        self._device_address = device.mac_address
        self._attr_translation_key = "channel"
        self._attr_translation_placeholders = {"channel_id": str(channel)}
        self._attr_unique_id = f"{self._device_address}_{channel}"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return super().available and self._attr_available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_EFFECT in kwargs:
            await self._device.set_light_mode(EFFECT_TO_LIGHT_MODE[kwargs[ATTR_EFFECT]])
            return
        if ATTR_BRIGHTNESS in kwargs:
            if self._device.light_mode == LightMode.DAYCL_MODE:
                await self._device.set_light_mode(LightMode.MAN_MODE)
            await self._device.turn_on(
                int(brightness_to_value(BRIGHTNESS_SCALE, kwargs[ATTR_BRIGHTNESS])),
                self._channel,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        if self._device.light_mode == LightMode.DAYCL_MODE:
            await self._device.set_light_mode(LightMode.MAN_MODE)
        await self._device.turn_off(self._channel)

    def _handle_coordinator_update(self) -> None:
        device = cast(
            EheimDigitalClassicLEDControl, self.coordinator.data[self._device_address]
        )
        light_level = device.light_level[self._channel]

        self._attr_available = light_level is not None
        self._attr_is_on = light_level > 0 if light_level is not None else None
        self._attr_brightness = (
            value_to_brightness(BRIGHTNESS_SCALE, light_level)
            if light_level is not None
            else None
        )
        self._attr_effect = (
            DAYCL_MODE if device.light_mode == LightMode.DAYCL_MODE else EFFECT_OFF
        )
        self.async_write_ha_state()
