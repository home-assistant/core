"""EHEIM Digital lights."""

from typing import Any

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import EheimDigitalConfigEntry
from .const import EFFECT_DAYCL_MODE, EFFECT_TO_LIGHT_MODE
from .coordinator import EheimDigitalUpdateCoordinator
from .entity import EheimDigitalEntity

BRIGHTNESS_SCALE = (1, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EheimDigitalConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EHEIM Digital lights based on a config entry."""
    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def check_devices() -> None:
        if len(coordinator.hub.devices) == 0:
            return

        registry = er.async_get(hass)
        existing_entities = er.async_entries_for_config_entry(registry, entry.entry_id)

        entities: list[EheimDigitalClassicLEDControlLight] = []

        new_classic_led_ctrl_devices = [
            device
            for device in coordinator.hub.devices.values()
            if isinstance(device, EheimDigitalClassicLEDControl)
            and device.mac_address not in known_devices
        ]

        known_classic_led_ctrl_devices = [
            device
            for device in coordinator.hub.devices.values()
            if isinstance(device, EheimDigitalClassicLEDControl)
            and device.mac_address in known_devices
        ]

        for device in new_classic_led_ctrl_devices:
            for channel in range(2):
                if len(device.tankconfig[channel]) > 0:
                    entities.append(
                        EheimDigitalClassicLEDControlLight(coordinator, device, channel)
                    )
                    known_devices.add(device.mac_address)
        for device in known_classic_led_ctrl_devices:
            for channel in range(2):
                if len(device.tankconfig[channel]) == 0:
                    for entity in existing_entities:
                        if entity.unique_id == f"{device.mac_address}_{channel}":
                            registry.async_remove(entity.entity_id)
                elif (
                    len(
                        [
                            entity
                            for entity in existing_entities
                            if entity.unique_id == f"{device.mac_address}_{channel}"
                        ]
                    )
                    == 0
                ):
                    entities.append(
                        EheimDigitalClassicLEDControlLight(coordinator, device, channel)
                    )

        async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(check_devices))
    check_devices()


class EheimDigitalClassicLEDControlLight(
    EheimDigitalEntity[EheimDigitalClassicLEDControl], LightEntity
):
    """Represent a EHEIM Digital classicLEDcontrol light."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_effect_list = [EFFECT_DAYCL_MODE]
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_translation_key = "channel"

    def __init__(
        self,
        coordinator: EheimDigitalUpdateCoordinator,
        device: EheimDigitalClassicLEDControl,
        channel: int,
    ) -> None:
        """Initialize an EHEIM Digital classicLEDcontrol light entity."""
        super().__init__(coordinator, device)
        self._channel = channel
        self._attr_translation_placeholders = {"channel_id": str(channel)}
        self._attr_unique_id = f"{self._device_address}_{channel}"
        self._async_update_attrs()

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

    def _async_update_attrs(self) -> None:
        light_level = self._device.light_level[self._channel]

        self._attr_available = light_level is not None
        self._attr_is_on = light_level > 0 if light_level is not None else None
        self._attr_brightness = (
            value_to_brightness(BRIGHTNESS_SCALE, light_level)
            if light_level is not None
            else None
        )
        self._attr_effect = (
            EFFECT_DAYCL_MODE
            if self._device.light_mode == LightMode.DAYCL_MODE
            else EFFECT_OFF
        )
